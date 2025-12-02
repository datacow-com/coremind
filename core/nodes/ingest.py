from core.embedding.provider_embedder import Embedder
from core.loaders.visual_pdf_loader import ParsingRule, VisualPDFLoader
from core.state import ProcessedChunk, RAGState
from core.storage.index_router import add as add_index
from core.storage.keyword_index import get_keyword_index


async def ingest(state: RAGState) -> dict:
    docs = state.get("documents") or []
    chunks: list[ProcessedChunk] = []
    if docs:
        loader = VisualPDFLoader(ParsingRule())
        for d in docs:
            path = d.get("file_path") or ""
            if path:
                loaded = await loader.process_pdf(path)
                chunks.extend(loaded)
        emb = Embedder(dim=256)
        kw = get_keyword_index()
        for ch in chunks:
            vec = emb.embed(ch.get("content", ""))
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
