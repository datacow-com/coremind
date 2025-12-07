from __future__ import annotations

from typing import Any

from core.storage.kb_config import load_kb_config
from server.config import settings


def merge_kb_params(meta: dict[str, Any]) -> dict[str, Any]:
    """
    Merge KB config and request metadata for retrieval/rerank parameters.

    Precedence: request metadata > KB config > settings default.
    """
    kb_name = meta.get("kb_name") or None
    try:
        kb_cfg = load_kb_config(str(kb_name)) if kb_name else {}
    except Exception:
        # 防御性兜底：避免不存在/损坏的 KB 配置导致链路中断
        kb_cfg = {}

    def pick(key: str, cast=float, default: Any | None = None):
        if key in meta and meta[key] is not None:
            try:
                return cast(meta[key])
            except Exception:
                return meta[key]
        if kb_cfg and key in kb_cfg and kb_cfg[key] is not None:
            try:
                return cast(kb_cfg[key])
            except Exception:
                return kb_cfg[key]
        return getattr(settings, key, default)

    out = dict(meta)
    out["vector_weight"] = pick("vector_weight", float, getattr(settings, "vector_weight", 0.6))
    out["keyword_weight"] = pick("keyword_weight", float, getattr(settings, "keyword_weight", 0.4))
    out["reranker_filter_threshold"] = pick(
        "reranker_filter_threshold",
        float,
        getattr(settings, "reranker_filter_threshold", 0.2),
    )
    out["rerank_base_weight"] = pick(
        "rerank_base_weight", float, getattr(settings, "rerank_base_weight", 0.7)
    )
    out["rerank_model_weight"] = pick(
        "rerank_model_weight", float, getattr(settings, "rerank_model_weight", 0.3)
    )
    out["top_k"] = int(pick("top_k", int, getattr(settings, "top_k_default", 5)))
    out["candidate_k"] = int(pick("candidate_k", int, getattr(settings, "candidate_k", 50)))
    out["rrf_k"] = int(pick("rrf_k", int, getattr(settings, "rrf_k", 60)))
    out["web_search_max_results"] = int(pick("web_search_max_results", int, 5))
    out["web_search_timeout"] = float(pick("web_search_timeout", float, 8.0))
    out["web_search_enabled"] = bool(
        pick("web_search_enabled", bool, getattr(settings, "web_search_enabled", True))
    )
    out["web_search_provider"] = pick(
        "web_search_provider", str, getattr(settings, "web_search_provider", None)
    )
    out["vector_backend"] = pick(
        "vector_backend",
        str,
        getattr(settings, "force_vector_backend", None)
        or getattr(settings, "vector_backend", None),
    )
    out["collection_name"] = pick("collection_name", str, None)
    return out
