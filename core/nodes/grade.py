from typing import Dict
from core.state import RAGState

async def grade(state: RAGState) -> Dict:
    web_needed = not bool(state.get("retrieved_chunks"))
    return {"web_search_needed": web_needed, "step": "grade"}
