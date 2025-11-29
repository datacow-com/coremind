from typing import Dict, List
from core.state import RAGState, RetrievedChunk
from core.reranker.cross_encoder import Reranker


async def rerank(state: RAGState) -> Dict:
    query = state.get("query", "")
    items: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    texts = [it.get("content", "") for it in items]
    rr = Reranker()
    scores = rr.score(query, texts)
    scored: List[RetrievedChunk] = []
    for it, rr_s in zip(items, scores):
        base = float(it.get("score", 0.0))
        it["rerank_score"] = 0.7 * base + 0.3 * float(rr_s)
        scored.append(it)
    scored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return {"retrieved_chunks": scored, "step": "rerank"}
