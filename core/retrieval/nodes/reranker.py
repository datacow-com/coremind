"""
Reranker Node - Cross-encoder reranking for search results.

Features:
- Multiple reranker providers (Cohere, CrossEncoder, HTTP)
- Configurable threshold filtering
- Fallback chain support
- Instance caching (P1 Fix #10)
"""

import time
from typing import Any

from core.reranker.registry import get_reranker
from core.state import RetrievalState


# P1 Fix #10: Reranker instance cache with TTL
_RERANKER_CACHE: dict[str, tuple[Any, float]] = {}
_CACHE_TTL = 300  # 5 minutes


class CrossEncoderReranker:
    """
    Cross-encoder reranker with caching.
    
    P1 Fix #10: Uses cached reranker instances to avoid repeated DB queries.
    """
    
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state["strategy_config"]
        query = state["input_query"]
        fused_docs = state["fused_results"]

        if not fused_docs:
            state["reranked_results"] = []
            state["is_relevant"] = False
            return state

        texts = [doc["content"] for doc in fused_docs]
        
        # P1 Fix #10: Use cached reranker with TTL
        reranker = await self._get_cached_reranker(cfg)

        # Reranker scoring
        scores = reranker.score(query, texts)

        # Update scores and sort
        reranked = []
        threshold = cfg.get("rerank_threshold", 0.0)  # Loose threshold by default

        for doc, score in zip(fused_docs, scores, strict=False):
            doc["rerank_score"] = score
            if score >= threshold:
                reranked.append(doc)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)

        state["reranked_results"] = reranked
        state["is_relevant"] = len(reranked) > 0
        
        # P1 Fix #11: Calculate confidence based on rerank scores
        if reranked:
            avg_score = sum(d["rerank_score"] for d in reranked[:3]) / min(3, len(reranked))
            state["retrieval_confidence"] = min(1.0, max(0.0, avg_score))
        else:
            state["retrieval_confidence"] = 0.0

        return state
    
    async def _get_cached_reranker(self, cfg: dict[str, Any]) -> Any:
        """Get reranker with TTL caching."""
        global _RERANKER_CACHE
        
        provider = cfg.get("reranker_provider", "cross_encoder")
        model_id = cfg.get("reranker_model")
        fallback_models = cfg.get("fallback_rerank_models") or []
        
        cache_key = f"{provider}:{model_id}:{','.join(fallback_models)}"
        current_time = time.time()
        
        # Check cache with TTL
        if cache_key in _RERANKER_CACHE:
            reranker, cached_time = _RERANKER_CACHE[cache_key]
            if current_time - cached_time < _CACHE_TTL:
                return reranker
        
        # Create new reranker
        reranker = await get_reranker(
            provider=provider,
            model_id=model_id,
            fallback_models=fallback_models,
        )
        
        # Cache it
        _RERANKER_CACHE[cache_key] = (reranker, current_time)
        
        return reranker


def clear_reranker_cache() -> None:
    """Clear the reranker cache."""
    global _RERANKER_CACHE
    _RERANKER_CACHE.clear()
