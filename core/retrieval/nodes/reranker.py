from core.reranker.registry import get_reranker
from core.state import RetrievalState


class CrossEncoderReranker:
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state["strategy_config"]
        query = state["input_query"]
        fused_docs = state["fused_results"]

        if not fused_docs:
            state["reranked_results"] = []
            state["is_relevant"] = False
            return state

        texts = [doc["content"] for doc in fused_docs]
        reranker = await get_reranker(
            provider=cfg.get("reranker_provider", "cross_encoder"),
            model_id=cfg.get("reranker_model"),
            fallback_models=cfg.get("fallback_rerank_models") or [],
        )

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

        return state
