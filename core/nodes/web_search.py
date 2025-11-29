from typing import Dict, List
from core.state import RAGState, RetrievedChunk


async def web_search(state: RAGState) -> Dict:
    query = state.get("query", "")
    chunks: List[RetrievedChunk] = []
    try:
        from backend.src.llm_service import LLMService
        svc = LLMService()
        results = await svc.web_search(query, max_results=5)
        for i, r in enumerate(results):
            chunks.append({
                "id": f"web-{i}",
                "content": r.content,
                "page_num": 0,
                "doc_id": r.url,
                "chunk_index": i,
                "metadata": {"type": "web", "title": r.title, "url": r.url},
                "score": float(r.relevance_score),
                "rerank_score": None,
            })
    except Exception:
        pass
    return {"retrieved_chunks": chunks, "step": "web_search"}
