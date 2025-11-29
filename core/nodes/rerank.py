from typing import Dict, List
from core.state import RAGState, RetrievedChunk

async def rerank(state: RAGState) -> Dict:
    items: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    return {"retrieved_chunks": items, "step": "rerank"}
