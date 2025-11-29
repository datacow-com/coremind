from typing import Dict, List
from core.state import RAGState, RetrievedChunk


async def grade(state: RAGState) -> Dict:
    items: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    if not items:
        return {"web_search_needed": True, "step": "grade"}
    max_score = max([float(x.get("rerank_score") or x.get("score") or 0.0) for x in items])
    threshold = 0.35
    return {"web_search_needed": max_score < threshold, "step": "grade"}
