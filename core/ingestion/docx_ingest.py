import os
import zipfile
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict


class DocxIngestState(TypedDict):
    file_path: str
    md: str | None
    meta: dict[str, Any]


def _text_elems(elem) -> list[str]:
    texts: list[str] = []
    for t in elem.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
        if t.text:
            texts.append(t.text)
    return texts


def _parse_docx_xml(xml_bytes: bytes) -> str:
    try:
        from defusedxml import ElementTree as ET
    except Exception:
        import xml.etree.ElementTree as ET
    md_lines: list[str] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return "# Document\n\nExtraction failed."
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    # tables
    for tbl in root.findall(f".//{ns}tbl"):
        rows = []
        for tr in tbl.findall(f".//{ns}tr"):
            cells = []
            for tc in tr.findall(f".//{ns}tc"):
                texts = _text_elems(tc)
                cells.append(" ".join(texts))
            if cells:
                rows.append(cells)
        if rows:
            # markdown table
            md_lines.append("")
            md_lines.append("| " + " | ".join(rows[0]) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
            for r in rows[1:]:
                md_lines.append("| " + " | ".join(r) + " |")
            md_lines.append("")
    # paragraphs
    for p in root.findall(f".//{ns}p"):
        texts = _text_elems(p)
        line = " ".join(texts).strip()
        if not line:
            continue
        if len(line) < 80:
            md_lines.append(f"## {line}")
        else:
            md_lines.append(line)
    out = "\n\n".join(md_lines)
    if not out.strip():
        return "# Document\n\n(No content)"
    return out


async def read_docx_to_md(state: DocxIngestState) -> DocxIngestState:
    fp = state.get("file_path") or ""
    if not fp:
        state["md"] = state.get("md") or ""
        return state
    md = ""
    try:
        with zipfile.ZipFile(fp, "r") as z:
            with z.open("word/document.xml") as f:
                xml_bytes = f.read()
                md = _parse_docx_xml(xml_bytes)
    except Exception:
        md = state.get("md") or ""
    state["md"] = md
    return state


async def store_md(state: DocxIngestState) -> DocxIngestState:
    base_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_path") or "document.docx"))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    # write to index
    try:
        from core.embedding.registry import get_embedder
        from core.storage.index_router import add as index_add

        md_text = state.get("md") or ""
        paras = [p.strip() for p in md_text.split("\n\n") if p.strip()]
        emb = get_embedder()
        vecs = None
        try:
            vecs = await emb.embed_batch(paras) if hasattr(emb, "embed_batch") else None
        except Exception:
            vecs = None
        for i, chunk in enumerate(paras):
            import asyncio

            vec = None
            if vecs is not None and len(vecs) > i:
                vec = vecs[i]
            else:
                vec = await asyncio.to_thread(emb.embed, chunk)
            meta = {
                "id": f'{state.get("file_path")}-chunk-{i}',
                "content": chunk,
                "page_num": 1,
                "doc_id": state.get("file_path") or "docx",
                "chunk_index": i,
                "metadata": {"type": "docx", "bbox": None, "confidence": 0.0},
            }
            index_add(vec, meta)
    except Exception:
        pass
    return state


def create_docx_ingest_graph():
    g = StateGraph(DocxIngestState)
    g.add_node("read_docx_to_md", read_docx_to_md)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_docx_to_md")
    g.add_edge("read_docx_to_md", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
