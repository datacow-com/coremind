import time

from core.reranker.cross_encoder import Reranker
from core.state import RAGState, RetrievedChunk
from server.config import settings


async def rerank(state: RAGState) -> dict:
    query = state.get("query", "")
    items: list[RetrievedChunk] = state.get("retrieved_chunks", [])
    texts = [it.get("content", "") for it in items]
    rr = Reranker()
    t0 = time.perf_counter()
    scores = rr.score(query, texts)
    scored: list[RetrievedChunk] = []
    for it, rr_s in zip(items, scores, strict=False):
        base = float(it.get("score", 0.0))
        it["rerank_score"] = 0.7 * base + 0.3 * float(rr_s)
        scored.append(it)
    scored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    thr = float(settings.reranker_filter_threshold)
    scored = [it for it in scored if float(it.get("rerank_score") or 0.0) >= thr]
    top_k = int((state.get("metadata") or {}).get("top_k") or settings.top_k_default)
    scored = scored[:top_k]
    dur = int((time.perf_counter() - t0) * 1000)
    avg = (
        (sum([float(it.get("rerank_score") or 0.0) for it in scored]) / max(len(scored), 1))
        if scored
        else 0.0
    )
    return {
        "retrieved_chunks": scored,
        "step": "rerank",
        "metrics": {"rerank": {"count": len(scored), "avg_score": avg, "duration_ms": dur}},
    }
