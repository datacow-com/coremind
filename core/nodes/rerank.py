from typing import Dict, List
from core.state import RAGState, RetrievedChunk


def _overlap_score(query: str, text: str) -> float:
    q = set([w for w in query.lower().split() if w])
    t = set([w for w in text.lower().split() if w])
    if not q:
        return 0.0
    return len(q & t) / len(q)


async def rerank(state: RAGState) -> Dict:
    query = state.get("query", "")
    items: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    scored: List[RetrievedChunk] = []
    for it in items:
        base = float(it.get("score", 0.0))
        ov = _overlap_score(query, it.get("content", ""))
        it["rerank_score"] = 0.7 * base + 0.3 * ov
        scored.append(it)
    scored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return {"retrieved_chunks": scored, "step": "rerank"}
