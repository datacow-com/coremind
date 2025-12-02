import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict


class MarkdownIngestState(TypedDict):
    md: str | None
    file_path: str | None
    meta: dict[str, Any]


async def read_or_pass(state: MarkdownIngestState) -> MarkdownIngestState:
    fp = state.get("file_path")
    if fp and os.path.exists(fp):
        try:
            with open(fp, encoding="utf-8") as f:
                state["md"] = f.read()
        except Exception:
            state["md"] = state.get("md") or ""
    # write to index when md is present
    try:
        from core.embedding.provider_embedder import Embedder
        from core.storage.index_router import add as index_add
        from core.storage.keyword_index import get_keyword_index

        md = state.get("md") or ""
        paras = [p.strip() for p in md.split("\n\n") if p.strip()]
        emb = Embedder(dim=256)
        kw = get_keyword_index()
        for i, chunk in enumerate(paras):
            vec = emb.embed(chunk)
            meta = {
                "id": f"{fp}-chunk-{i}",
                "content": chunk,
                "page_num": 1,
                "doc_id": fp or "md",
                "chunk_index": i,
                "metadata": {"type": "markdown", "bbox": None, "confidence": 0.0},
            }
            index_add(vec, meta)
            kw.add(chunk, meta)
    except Exception:
        pass
    return state


async def store_md(state: MarkdownIngestState) -> MarkdownIngestState:
    base_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_path") or "document.md"))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    return state


def create_markdown_ingest_graph():
    g = StateGraph(MarkdownIngestState)
    g.add_node("read_or_pass", read_or_pass)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_or_pass")
    g.add_edge("read_or_pass", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
