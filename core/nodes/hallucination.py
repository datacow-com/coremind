from typing import Dict
from core.state import RAGState

async def hallucination(state: RAGState) -> Dict:
    score = 0.0
    return {"hallucination_score": score, "step": "hallucination"}
