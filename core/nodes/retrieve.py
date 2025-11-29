from typing import Dict, List
from core.state import RAGState, RetrievedChunk
from core.embedding.provider_embedder import Embedder
from core.storage.index_router import search as search_index
from core.storage.keyword_index import get_keyword_index
import os


async def retrieve(state: RAGState) -> Dict:
    query = state.get("query", "")
    if not query:
        return {"retrieved_chunks": [], "step": "retrieval"}

    emb = Embedder(dim=256)
    qvec = emb.embed(query)
    v_weight = float(os.environ.get("VECTOR_WEIGHT", "0.6"))
    k_weight = float(os.environ.get("KEYWORD_WEIGHT", "0.4"))
    vector_results = search_index(qvec, top_k=5)
    kw = get_keyword_index()
    keyword_results = kw.search(query, top_k=5)

    fused: Dict[str, RetrievedChunk] = {}
    def push(meta, score):
        rid = meta.get("id")
        existing = fused.get(rid)
        if not existing:
            fused[rid] = {
                "id": rid,
                "content": meta.get("content"),
                "page_num": meta.get("page_num"),
                "doc_id": meta.get("doc_id"),
                "chunk_index": meta.get("chunk_index"),
                "metadata": meta.get("metadata", {}),
                "score": float(score),
                "rerank_score": None,
            }
        else:
            existing["score"] = max(existing.get("score", 0.0), float(score))

    for meta, s in vector_results:
        push(meta, v_weight * float(s))
    for meta, s in keyword_results:
        push(meta, k_weight * float(s))

    results: List[RetrievedChunk] = list(fused.values())
    
    retrieved: List[RetrievedChunk] = sorted(results, key=lambda x: x.get("score", 0.0), reverse=True)[:5]

    return {"retrieved_chunks": retrieved, "step": "retrieval"}
