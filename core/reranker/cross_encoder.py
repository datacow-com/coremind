"""
CrossEncoder Reranker with Singleton Pattern.
Loads the model once and reuses it across all requests.
"""

import os
import threading

# Singleton cache
_MODEL_CACHE: dict[str, "Reranker"] = {}
_CACHE_LOCK = threading.Lock()


def get_singleton_reranker(model_name: str | None = None) -> "Reranker":
    """Get or create a singleton Reranker instance for the given model."""
    name = model_name or os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

    with _CACHE_LOCK:
        if name not in _MODEL_CACHE:
            _MODEL_CACHE[name] = Reranker(model_name=name, _skip_singleton=True)
        return _MODEL_CACHE[name]


class Reranker:
    """
    CrossEncoder-based Reranker with lazy loading and caching.

    Performance Optimization:
    - Model is loaded only once per model_name
    - Subsequent calls reuse the cached model
    """

    def __init__(self, model_name: str | None = None, _skip_singleton: bool = False):
        """
        Initialize the Reranker.

        Args:
            model_name: The model to use. Defaults to BAAI/bge-reranker-v2-m3
            _skip_singleton: Internal flag - if True, creates a new instance.
                           If False, returns from singleton cache.
        """
        if not _skip_singleton:
            # Redirect to singleton - this makes the class safe for naive instantiation
            cached = get_singleton_reranker(model_name)
            self._ce = cached._ce
            self._model_name = cached._model_name
            return

        self._ce = None
        self._model_name = model_name or os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

        # Only load if explicitly enabled
        if os.environ.get("USE_CROSS_ENCODER") == "1":
            try:
                from sentence_transformers import CrossEncoder

                self._ce = CrossEncoder(self._model_name)
            except Exception:
                self._ce = None

    def _fallback_scores(self, query: str, texts: list[str]) -> list[float]:
        """Fallback scoring using token overlap when model is unavailable."""
        import re

        def norm(s: str) -> list[str]:
            s = (s or "").lower()
            s = re.sub(r"[\.,;:!\?\-_/\\\(\)\[\]{}<>\|\^\$\*\+\=\"]", " ", s)
            return [w for w in s.split() if w]

        q = set(norm(query))
        out: list[float] = []
        for t in texts:
            T = set(norm(t or ""))
            if not q:
                out.append(0.0)
            else:
                out.append(len(q & T) / len(q))
        return out

    def score(self, query: str, texts: list[str]) -> list[float]:
        """Score query-text pairs using CrossEncoder or fallback."""
        if not texts:
            return []
        if self._ce is None:
            return self._fallback_scores(query, texts)
        try:
            pairs = [(query, t or "") for t in texts]
            raw = self._ce.predict(pairs)
            # Normalize to 0..1
            mn = float(min(raw))
            mx = float(max(raw))
            if mx - mn < 1e-6:
                return [0.5 for _ in raw]
            return [float((r - mn) / (mx - mn)) for r in raw]
        except Exception:
            return self._fallback_scores(query, texts)
