import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.embedding.registry import get_embedder
from core.loaders.visual_pdf_loader import ParsingRule, VisualPDFLoader
from core.state import ProcessedChunk
from core.storage.index_router import add as add_index
from core.storage.keyword_index import get_keyword_index


class IngestIndexState(TypedDict):
    file_path: str
    chunks: list[ProcessedChunk]
    meta: dict[str, Any]


async def parse_pdf(state: IngestIndexState) -> IngestIndexState:
    fp = state["file_path"]
    from core.storage.kb_config import load_kb_config

    meta = state.get("meta") or {}
    kb_name = meta.get("kb_name")
    semantic = False
    denoise = False
    yolo_enabled = None
    layoutlm_enabled = None
    layoutlm_class = None
    if kb_name:
        try:
            kbc = load_kb_config(str(kb_name))
            ip = kbc.get("ingestion_pipeline") or {}
            semantic = bool(ip.get("semantic_chunking", False))
            denoise = bool(ip.get("parser_denoise", False))
            yolo_enabled = ip.get("yolo_enabled")
            layoutlm_enabled = ip.get("layoutlm_enabled")
        except Exception:
            pass
    if layoutlm_enabled:
        try:
            from server.config import settings

            layoutlm_class = getattr(settings, "layoutlm_class_model", None)
            if layoutlm_class:
                os.environ["LAYOUTLM_CLASS_MODEL"] = str(layoutlm_class)
        except Exception:
            pass
    else:
        try:
            if "LAYOUTLM_CLASS_MODEL" in os.environ:
                os.environ.pop("LAYOUTLM_CLASS_MODEL")
        except Exception:
            pass
    if yolo_enabled:
        try:
            from server.config import settings

            model = getattr(settings, "yolo_model", None)
            if model:
                os.environ["YOLO_ENABLED"] = "1"
                os.environ["YOLO_MODEL"] = str(model)
        except Exception:
            pass
    else:
        try:
            if "YOLO_ENABLED" in os.environ:
                os.environ.pop("YOLO_ENABLED")
            if "YOLO_MODEL" in os.environ:
                os.environ.pop("YOLO_MODEL")
        except Exception:
            pass
    loader = VisualPDFLoader(ParsingRule(semantic=semantic, denoise=denoise))
    chunks = await loader.process_pdf(fp)
    # enforce doc_id and block_type normalization
    doc_id_norm = os.path.splitext(os.path.basename(fp))[0]
    for ch in chunks:
        try:
            ch["doc_id"] = doc_id_norm
            md = ch.get("metadata") or {}
            bt = md.get("block_type") or md.get("type")
            md["block_type"] = bt or "paragraph"
            ch["metadata"] = md
        except Exception:
            pass
    state["chunks"] = chunks
    return state


async def embed_and_index(state: IngestIndexState) -> IngestIndexState:
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
    # 优先批量嵌入，失败再单条
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


def create_pdf_index_ingest_graph():
    g = StateGraph(IngestIndexState)
    g.add_node("parse_pdf", parse_pdf)
    g.add_node("embed_and_index", embed_and_index)
    g.set_entry_point("parse_pdf")
    g.add_edge("parse_pdf", "embed_and_index")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
