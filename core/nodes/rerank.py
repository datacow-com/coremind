import time

from core.reranker.registry import get_reranker
from core.state import RAGState, RetrievedChunk
from core.utils.trace import set_span_attrs
from server.config import settings


async def rerank(state: RAGState) -> dict:
    """LangGraph rerank 节点：基于模型分数与基础分融合，支持阈值过滤。"""
    query = state.get("query", "")
    items: list[RetrievedChunk] = state.get("retrieved_chunks", [])
    texts = [it.get("content", "") for it in items]
    provider = (state.get("metadata") or {}).get("reranker_provider")
    rr = await get_reranker(provider)
    t0 = time.perf_counter()
    scores = rr.score(query, texts)

    # min-max normalize both channels to 0..1
    def _norm(arr: list[float]) -> list[float]:
        if not arr:
            return []
        mn, mx = min(arr), max(arr)
        if mx - mn < 1e-6:
            return [0.5 for _ in arr]
        return [(x - mn) / (mx - mn) for x in arr]

    base_scores = [float(it.get("score", 0.0)) for it in items]
    norm_base = _norm(base_scores)
    norm_model = _norm([float(s) for s in scores])
    meta = state.get("metadata", {}) or {}
    base_w = float(meta.get("rerank_base_weight") or getattr(settings, "rerank_base_weight", 0.7))
    model_w = float(
        meta.get("rerank_model_weight") or getattr(settings, "rerank_model_weight", 0.3)
    )
    total_w = base_w + model_w or 1.0
    base_w /= total_w
    model_w /= total_w

    scored: list[RetrievedChunk] = []
    for idx, (it, nb, nm) in enumerate(zip(items, norm_base, norm_model, strict=False)):
        it["rerank_score"] = base_w * nb + model_w * nm
        scored.append(it)
    scored.sort(key=lambda x: float(x.get("rerank_score") or 0.0), reverse=True)
    try:
        thr = float(meta.get("reranker_filter_threshold"))
    except Exception:
        thr = float(settings.reranker_filter_threshold)
    scored = [it for it in scored if float(it.get("rerank_score") or 0.0) >= thr]
    top_k = int((state.get("metadata") or {}).get("top_k") or settings.top_k_default)
    scored = scored[:top_k]
    dur = int((time.perf_counter() - t0) * 1000)
    avg = (
        (sum([float(it.get("rerank_score") or 0.0) for it in scored]) / max(len(scored), 1))
        if scored
        else 0.0
    )
    set_span_attrs(
        {
            "rerank.provider": provider or "auto",
            "rerank.base_weight": base_w,
            "rerank.model_weight": model_w,
            "rerank.threshold": thr,
            "rerank.count": len(scored),
            "rerank.duration_ms": dur,
        }
    )
    return {
        "retrieved_chunks": scored,
        "step": "rerank",
        "metrics": {"rerank": {"count": len(scored), "avg_score": avg, "duration_ms": dur}},
    }
