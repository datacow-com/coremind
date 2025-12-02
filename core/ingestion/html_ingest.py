import os
from html.parser import HTMLParser
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from server.config import settings


class HtmlIngestState(TypedDict):
    file_path: str
    md: str | None
    meta: dict[str, Any]


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"h1", "h2", "h3"}:
            self.texts.append("\n# ")
        elif tag in {"li"}:
            self.texts.append("\n- ")
        elif tag in {"p"}:
            self.texts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            s = (data or "").strip()
            if s:
                self.texts.append(s)


async def read_html_to_md(state: HtmlIngestState) -> HtmlIngestState:
    fp = state.get("file_path")
    md = ""
    try:
        with open(fp, encoding="utf-8", errors="ignore") as f:
            html = f.read()
        parser = _TextExtractor()
        parser.feed(html)
        txt = "".join(parser.texts)
        lines = [line.strip() for line in txt.splitlines() if line.strip()]
        md = "\n".join(lines)
    except Exception:
        md = state.get("md") or ""
    state["md"] = md
    return state


async def store_md(state: HtmlIngestState) -> HtmlIngestState:
    base_dir = settings.uploads_dir_resolved
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_path") or "page.html"))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
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
                "id": f"{state.get('file_path')}-chunk-{i}",
                "content": chunk,
                "page_num": 1,
                "doc_id": state.get("file_path") or "html",
                "chunk_index": i,
                "metadata": {"type": "html", "bbox": None, "confidence": 0.0},
            }
            index_add(vec, meta)
            kw.add(chunk, meta)
    except Exception:
        pass
    return state


def create_html_ingest_graph():
    g = StateGraph(HtmlIngestState)
    g.add_node("read_html_to_md", read_html_to_md)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_html_to_md")
    g.add_edge("read_html_to_md", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
