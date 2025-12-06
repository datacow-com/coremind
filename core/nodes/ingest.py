from core.embedding.provider_embedder import Embedder
from core.loaders.visual_pdf_loader import ParsingRule, VisualPDFLoader
from core.state import ProcessedChunk, RAGState
from core.storage.index_router import add as add_index
from core.storage.keyword_index import get_keyword_index


async def ingest(state: RAGState) -> dict:
    docs = state.get("documents") or []
    chunks: list[ProcessedChunk] = []
    if docs:
        import os

        from server.config import settings

        sem = bool(
            getattr(settings, "semantic_chunking", False) or os.environ.get("SEMANTIC_CHUNKING")
        )
        den = bool(getattr(settings, "parser_denoise", False) or os.environ.get("PARSER_DENOISE"))
        loader = VisualPDFLoader(ParsingRule(semantic=sem, denoise=den))
        for d in docs:
            path = d.get("file_path") or ""
            if path:
                loaded = await loader.process_pdf(path)
                chunks.extend(loaded)
        emb = Embedder(dim=256)
        kw = get_keyword_index()
        for ch in chunks:
            import asyncio

            vec = await asyncio.to_thread(emb.embed, ch.get("content", ""))
            add_index(
                vec,
                {
                    "id": ch.get("id"),
                    "content": ch.get("content"),
                    "page_num": ch.get("page_num"),
                    "doc_id": ch.get("doc_id"),
                    "chunk_index": ch.get("chunk_index"),
                    "metadata": ch.get("metadata", {}),
                },
            )
            kw.add(
                ch.get("content", ""),
                {
                    "id": ch.get("id"),
                    "content": ch.get("content"),
                    "page_num": ch.get("page_num"),
                    "doc_id": ch.get("doc_id"),
                    "chunk_index": ch.get("chunk_index"),
                    "metadata": ch.get("metadata", {}),
                },
            )
    return {"chunks": chunks, "step": "ingestion"}


import asyncio

try:
    asyncio.get_event_loop()
except Exception:
    asyncio.set_event_loop(asyncio.new_event_loop())
