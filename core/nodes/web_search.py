from typing import Dict, List
import time
from core.state import RAGState, RetrievedChunk


async def web_search(state: RAGState) -> Dict:
    t0 = time.perf_counter()
    query = state.get("query", "")
    chunks: List[RetrievedChunk] = []
    web_results: List[Dict] = []
    try:
        from core.tools.web_search_provider import choose_provider, simple_overlap_score
        provider = choose_provider()
        results = await provider.search(query, max_results=5)
        for i, r in enumerate(results):
            web_results.append(r)
            chunks.append({
                "id": f"web-{i}",
                "content": (r.get("title") or r.get("snippet") or r.get("url") or ""),
                "page_num": 0,
                "doc_id": r.get("url") or "",
                "chunk_index": i,
                "metadata": {"type": "web", "title": r.get("title"), "url": r.get("url")},
                "score": float(simple_overlap_score(query, (r.get("title") or "") + " " + (r.get("snippet") or ""))),
                "rerank_score": None,
            })
    except Exception:
        web_results = []
    dur = int((time.perf_counter() - t0) * 1000)
    return {"retrieved_chunks": chunks, "web_results": web_results, "step": "web_search", "metrics": {"web_search": {"count": len(chunks), "duration_ms": dur}}}
