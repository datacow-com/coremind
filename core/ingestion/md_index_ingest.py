from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.embedding.registry import get_embedder
from core.state import ProcessedChunk
from core.storage.index_router import add as add_index
from core.storage.keyword_index import get_keyword_index


class MdIndexState(TypedDict):
    md: str
    doc_id: str
    chunks: list[ProcessedChunk]
    meta: dict[str, Any]


def _chunk_text(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: list[str] = []
    buf = []
    acc = 0
    for p in parts:
        l = len(p)
        if acc + l <= 1200:
            buf.append(p)
            acc += l
        else:
            out.append("\n\n".join(buf))
            buf = [p]
            acc = l
    if buf:
        out.append("\n\n".join(buf))
    return out


async def parse_md(state: MdIndexState) -> MdIndexState:
    text = state["md"]
    did = state["doc_id"]
    chunks: list[ProcessedChunk] = []
    paras = _chunk_text(text)
    for i, c in enumerate(paras):
        chunks.append(
            {
                "id": f"{did}:{i}",
                "content": c,
                "page_num": 0,
                "doc_id": did,
                "chunk_index": i,
                "metadata": {},
            }
        )
    state["chunks"] = chunks
    return state


async def embed_and_index(state: MdIndexState) -> MdIndexState:
    chunks = state.get("chunks", [])
    if not chunks:
        return state
    try:
        from core.storage.kb_config import load_kb_config
        kb_name = (state.get("meta") or {}).get("kb_name")
        mdl = None
        if kb_name:
            cfg = load_kb_config(str(kb_name)) or {}
            mdl = cfg.get("embedding_model") or None
    except Exception:
        mdl = None
    emb = get_embedder(model_name=mdl)
    kw = get_keyword_index()
    texts = [ch.get("content", "") for ch in chunks]
    vecs = None
    try:
        vecs = await emb.embed_batch(texts) if hasattr(emb, "embed_batch") else None
    except Exception:
        vecs = None
    for idx, ch in enumerate(chunks):
        import asyncio
        vec = None
        if vecs is not None and len(vecs) > idx:
            vec = vecs[idx]
        else:
            vec = await asyncio.to_thread(emb.embed, ch.get("content", ""))
        meta = {
            "id": ch.get("id"),
            "content": ch.get("content"),
            "page_num": ch.get("page_num"),
            "doc_id": ch.get("doc_id"),
            "chunk_index": ch.get("chunk_index"),
            "metadata": ch.get("metadata", {}),
            "kb_name": (state.get("meta") or {}).get("kb_name"),
        }
        add_index(vec, meta)
        kw.add(ch.get("content", ""), meta)
    return state


def create_md_index_ingest_graph():
    g = StateGraph(MdIndexState)
    g.add_node("parse_md", parse_md)
    g.add_node("embed_and_index", embed_and_index)
    g.set_entry_point("parse_md")
    g.add_edge("parse_md", "embed_and_index")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
