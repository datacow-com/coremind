from typing import Dict
from core.state import RAGState

async def web_search(state: RAGState) -> Dict:
    return {"step": "web_search"}
