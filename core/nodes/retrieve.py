from typing import Dict, List
from core.state import RAGState, RetrievedChunk
from core.embedding.simple_embedder import embed
from core.storage.local_index import get_index


async def retrieve(state: RAGState) -> Dict:
    query = state.get("query", "")
    if not query:
        return {"retrieved_chunks": [], "step": "retrieval"}

    qvec = embed(query)
    idx = get_index()
    results = idx.search(qvec, top_k=5)

    retrieved: List[RetrievedChunk] = []
    for meta, score in results:
        retrieved.append({
            "id": meta.get("id"),
            "content": meta.get("content"),
            "page_num": meta.get("page_num"),
            "doc_id": meta.get("doc_id"),
            "chunk_index": meta.get("chunk_index"),
            "metadata": meta.get("metadata", {}),
            "score": score,
            "rerank_score": None,
        })

    return {"retrieved_chunks": retrieved, "step": "retrieval"}
