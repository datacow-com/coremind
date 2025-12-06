import time

from core.state import RAGState, RetrievedChunk
from core.tools.web_search_provider import simple_overlap_score
from core.tools.web_search_registry import get_web_search_provider
from core.utils.trace import set_span_attrs


async def web_search(state: RAGState) -> dict:
    t0 = time.perf_counter()
    query = state.get("query", "")
    meta = state.get("metadata", {}) or {}
    chunks: list[RetrievedChunk] = []
    web_results: list[dict] = []
    provider_name = meta.get("web_search_provider") or None
    max_results = int(meta.get("web_search_max_results") or 5)
    max_results = max(1, min(max_results, 10))
    try:
        provider = get_web_search_provider(
            provider_name, timeout=float(meta.get("web_search_timeout") or 8.0)
        )
        results = await provider.search(query, max_results=max_results)
        seen = set()
        deduped = []
        for r in results:
            url = (r.get("url") or "").strip()
            title = (r.get("title") or "").strip()
            key = url or title
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(r)
        for i, r in enumerate(deduped):
            content = (
                (r.get("title") or "") + " " + (r.get("snippet") or "") + " " + (r.get("url") or "")
            )
            web_results.append(r)
            chunks.append(
                {
                    "id": f"web-{i}",
                    "content": content.strip(),
                    "page_num": 0,
                    "doc_id": r.get("url") or "",
                    "chunk_index": i,
                    "metadata": {
                        "type": "web",
                        "title": r.get("title"),
                        "url": r.get("url"),
                        "snippet": r.get("snippet"),
                    },
                    "score": float(simple_overlap_score(query, content)),
                    "rerank_score": None,
                }
            )
    except Exception as err:
        web_results = []
        set_span_attrs(
            {
                "web.provider": provider_name or "auto",
                "web.error": str(err),
            }
        )
    dur = int((time.perf_counter() - t0) * 1000)
    set_span_attrs(
        {
            "web.provider": provider_name or "auto",
            "web.count": len(chunks),
            "web.duration_ms": dur,
            "web.max_results": max_results,
        }
    )
    return {
        "retrieved_chunks": chunks,
        "web_results": web_results,
        "step": "web_search",
        "metrics": {"web_search": {"count": len(chunks), "duration_ms": dur}},
    }
