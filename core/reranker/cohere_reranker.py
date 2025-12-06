import os

import httpx


class CohereReranker:
    def __init__(self, model_name: str | None = None):
        self.model = model_name or os.environ.get("COHERE_RERANK_MODEL", "rerank-english-v3.0")
        self.key = os.environ.get("COHERE_API_KEY")

    def available(self) -> bool:
        return bool(self.key)

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        if not self.available():
            return [0.0 for _ in texts]
        docs = [{"text": t or ""} for t in texts]
        body = {"model": self.model, "query": query or "", "documents": docs}
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=15.0) as http:
                r = http.post("https://api.cohere.ai/v1/rerank", headers=headers, json=body)
                if r.status_code != 200:
                    return [0.0 for _ in texts]
                data = r.json()
                results = data.get("results") or []
                scores: list[float] = [0.0 for _ in texts]
                for item in results:
                    idx = int(item.get("index", 0))
                    sc = float(item.get("relevance_score", 0.0))
                    if 0 <= idx < len(scores):
                        scores[idx] = sc
                return scores
        except Exception:
            return [0.0 for _ in texts]
