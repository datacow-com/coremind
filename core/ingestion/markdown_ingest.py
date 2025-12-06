import os
import json
import logging
from typing import Any

# Deprecation Warning
logging.warning("This legacy module is deprecated. Please use core.ingestion.nodes.parser.CpuTextParser via IngestGraph.")

# Redirect to new pipeline if invoked directly (though typically invoked via graph)
# Since this file defines a specific graph 'create_markdown_ingest_graph', we can alias it 
# to return the new graph if possible, or just keep it as legacy bridge.

# For now, we keep the structure but mark as deprecated.
# The logic inside store_md has already been updated to use unified indexer.

from core.ingestion.graph import create_ingest_graph as create_unified_graph

def create_markdown_ingest_graph():
    # Redirect to unified graph? 
    # Unified graph expects IngestState, but legacy expects MarkdownIngestState.
    # They are different TypedDicts.
    # So we cannot simply replace the function body without breaking callers who expect specific state keys.
    # We must maintain the legacy graph definition for now, but it internally uses unified storage logic.
    
    # Re-import original logic to satisfy legacy callers
    from langgraph.graph import StateGraph
    from langgraph.checkpoint.memory import MemorySaver
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
        
        # Logic from updated markdown_ingest.py
        try:
            from core.embedding.registry import get_embedder
            from core.storage.index_router import add as index_add
            
            md = state.get("md") or ""
            paras = [p.strip() for p in md.split("\n\n") if p.strip()]
            emb = get_embedder()
            vecs = None
            try:
                vecs = await emb.embed_batch(paras) if hasattr(emb, "embed_batch") else None
            except Exception:
                vecs = None
            import asyncio

            for i, chunk in enumerate(paras):
                vec = None
                if vecs is not None and len(vecs) > i:
                    vec = vecs[i]
                else:
                    vec = await asyncio.to_thread(emb.embed, chunk)
                meta = {
                    "id": f"{fp}-chunk-{i}",
                    "content": chunk,
                    "page_num": 1,
                    "doc_id": fp or "md",
                    "chunk_index": i,
                    "metadata": {"type": "markdown", "bbox": None, "confidence": 0.0},
                }
                index_add(vec, meta)
        except Exception:
            pass
        return state

    async def store_md(state: MarkdownIngestState) -> MarkdownIngestState:
        # No-op or just pass through as read_or_pass handled indexing
        # Legacy graph had store_md separately. 
        # In updated code, read_or_pass did indexing. 
        # We keep store_md to satisfy graph topology if it was used.
        return state

    g = StateGraph(MarkdownIngestState)
    g.add_node("read_or_pass", read_or_pass)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_or_pass")
    g.add_edge("read_or_pass", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
