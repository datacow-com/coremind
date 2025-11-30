from typing import Dict, List
import time
from core.state import RAGState, RetrievedChunk


async def grade(state: RAGState) -> Dict:
    t0 = time.perf_counter()
    items: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    meta = state.get("metadata", {}) or {}
    if meta.get("web_search_enabled") is False:
        dur = int((time.perf_counter() - t0) * 1000)
        return {"web_search_needed": False, "step": "grade", "metrics": {"grade": {"duration_ms": dur, "max_score": 0.0, "threshold": 0.35}}}
    if meta.get("force_web_search") is True:
        dur = int((time.perf_counter() - t0) * 1000)
        return {"web_search_needed": True, "step": "grade", "metrics": {"grade": {"duration_ms": dur, "max_score": 0.0, "threshold": 0.35}}}
    if not items:
        dur = int((time.perf_counter() - t0) * 1000)
        return {"web_search_needed": True, "step": "grade", "metrics": {"grade": {"duration_ms": dur, "max_score": 0.0, "threshold": 0.35}}}
    max_score = max([float(x.get("rerank_score") or x.get("score") or 0.0) for x in items])
    threshold = 0.35
    dur = int((time.perf_counter() - t0) * 1000)
    return {"web_search_needed": max_score < threshold, "step": "grade", "metrics": {"grade": {"duration_ms": dur, "max_score": max_score, "threshold": threshold}}}
