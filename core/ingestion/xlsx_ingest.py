import os
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict


class XlsxIngestState(TypedDict):
    file_path: str
    md: str | None
    meta: dict[str, Any]


def _read_shared_strings(z: zipfile.ZipFile) -> list[str]:
    ss: list[str] = []
    try:
        with z.open("xl/sharedStrings.xml") as f:
            root = ET.fromstring(f.read())
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        for si in root.findall(f".//{ns}si"):
            # concatenate t nodes
            txt = "".join([t.text or "" for t in si.findall(f".//{ns}t")])
            ss.append(txt)
    except Exception:
        pass
    return ss


def _sheet_table(z: zipfile.ZipFile, name: str, shared: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        with z.open(name) as f:
            root = ET.fromstring(f.read())
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        for r in root.findall(f".//{ns}sheetData/{ns}row"):
            cells: list[str] = []
            for c in r.findall(f"{ns}c"):
                v = c.find(f"{ns}v")
                val = ""
                if v is not None and v.text is not None:
                    # type s => shared string index
                    if (c.get("t") or "") == "s":
                        try:
                            idx = int(v.text)
                            val = shared[idx] if 0 <= idx < len(shared) else ""
                        except Exception:
                            val = ""
                    else:
                        val = v.text
                cells.append(val)
            if cells:
                rows.append(cells)
    except Exception:
        pass
    return rows


async def read_xlsx_to_md(state: XlsxIngestState) -> XlsxIngestState:
    fp = state.get("file_path")
    md_lines: list[str] = []
    try:
        with zipfile.ZipFile(fp, "r") as z:
            shared = _read_shared_strings(z)
            sheet_names = sorted(
                [
                    n
                    for n in z.namelist()
                    if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
                ]
            )
            for idx, name in enumerate(sheet_names, start=1):
                rows = _sheet_table(z, name, shared)
                md_lines.append(f"# Sheet {idx}")
                if rows:
                    # header
                    md_lines.append("| " + " | ".join(rows[0]) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
                    for r in rows[1:]:
                        md_lines.append("| " + " | ".join(r) + " |")
                md_lines.append("")
    except Exception:
        pass
    md = "\n".join(md_lines) if md_lines else "# Sheets\n\n(No content)"
    state["md"] = md
    return state


async def store_md(state: XlsxIngestState) -> XlsxIngestState:
    base_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_path") or "book.xlsx"))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    # write to index
    try:
        from core.embedding.provider_embedder import Embedder
        from core.storage.index_router import add as index_add
        from core.storage.keyword_index import get_keyword_index

        md_text = state.get("md") or ""
        paras = [p.strip() for p in md_text.split("\n\n") if p.strip()]
        emb = Embedder(dim=256)
        kw = get_keyword_index()
        for i, chunk in enumerate(paras):
            vec = emb.embed(chunk)
            meta = {
                "id": f'{state.get("file_path")}-chunk-{i}',
                "content": chunk,
                "page_num": 1,
                "doc_id": state.get("file_path") or "xlsx",
                "chunk_index": i,
                "metadata": {"type": "xlsx", "bbox": None, "confidence": 0.0},
            }
            index_add(vec, meta)
            kw.add(chunk, meta)
    except Exception:
        pass
    return state


def create_xlsx_ingest_graph():
    g = StateGraph(XlsxIngestState)
    g.add_node("read_xlsx_to_md", read_xlsx_to_md)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_xlsx_to_md")
    g.add_edge("read_xlsx_to_md", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
