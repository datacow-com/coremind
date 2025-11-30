from typing import List
import os


class Reranker:
    def __init__(self, model_name: str | None = None):
        self._ce = None
        name = model_name or os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        try:
            from sentence_transformers import CrossEncoder
            self._ce = CrossEncoder(name)
        except Exception:
            self._ce = None

    def _fallback_scores(self, query: str, texts: List[str]) -> List[float]:
        q = set([w for w in query.lower().split() if w])
        out: List[float] = []
        for t in texts:
            T = set([w for w in (t or "").lower().split() if w])
            if not q:
                out.append(0.0)
            else:
                out.append(len(q & T) / len(q))
        return out

    def score(self, query: str, texts: List[str]) -> List[float]:
        if not texts:
            return []
        if self._ce is None:
            return self._fallback_scores(query, texts)
        try:
            pairs = [(query, t or "") for t in texts]
            raw = self._ce.predict(pairs)
            # normalize to 0..1
            mn = float(min(raw))
            mx = float(max(raw))
            if mx - mn < 1e-6:
                return [0.5 for _ in raw]
            return [float((r - mn) / (mx - mn)) for r in raw]
        except Exception:
            return self._fallback_scores(query, texts)
