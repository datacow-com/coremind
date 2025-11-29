from typing import Dict, List
from core.state import RAGState, RetrievedChunk

async def retrieve(state: RAGState) -> Dict:
    query = state.get("query", "")
    retrieved: List[RetrievedChunk] = [
        {
            "id": "q-0",
            "content": f"Placeholder context for: {query}",
            "page_num": 1,
            "doc_id": "inline",
            "chunk_index": 0,
            "metadata": {},
            "score": 0.5,
            "rerank_score": None,
        }
    ] if query else []
    return {"retrieved_chunks": retrieved, "step": "retrieval"}
