from typing import Dict, List
from core.state import RAGState, RetrievedChunk


async def hallucination(state: RAGState) -> Dict:
    answer = state.get("answer", "")
    chunks: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    context = "\n\n".join([c.get("content", "") for c in chunks])
    try:
        from backend.src.llm_service import LLMService
        svc = LLMService()
        score = await svc.check_hallucination(answer, context)
    except Exception:
        score = 0.5
    return {"hallucination_score": float(score), "step": "hallucination"}
