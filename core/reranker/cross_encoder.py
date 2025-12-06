import os


class Reranker:
    def __init__(self, model_name: str | None = None):
        self._ce = None
        name = model_name or os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        if os.environ.get("USE_CROSS_ENCODER") == "1":
            try:
                from sentence_transformers import CrossEncoder

                self._ce = CrossEncoder(name)
            except Exception:
                self._ce = None
        else:
            self._ce = None

    def _fallback_scores(self, query: str, texts: list[str]) -> list[float]:
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
