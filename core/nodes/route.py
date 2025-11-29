from typing import Dict
from core.state import RAGState

async def route(state: RAGState) -> Dict:
    return {"step": "route"}
