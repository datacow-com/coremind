import time

import httpx


class HttpReranker:
    """
    通用 HTTP reranker，兼容 vLLM/自研 rerank 接口：
    请求体：{"model": "...", "input": [{"text": t1}, {"text": t2}, ...]}
    返回：scores 数组或 results/index+score。
    """

    def __init__(self, base_url: str, api_key: str | None, model: str, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        body = {
            "model": self.model,
            "query": query or "",
            "input": [{"text": t or ""} for t in texts],
        }

        def _call() -> list[float]:
            url = f"{self.base_url}/rerank"
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(url, json=body, headers=self._headers())
                r.raise_for_status()
                data = r.json()
                # 支持两种返回格式：{"scores":[...]} 或 {"results":[{"index":0,"score":...}]}
                if "scores" in data and isinstance(data["scores"], list):
                    scores = data["scores"]
                else:
                    results = data.get("results") or data.get("data") or []
                    scores = [0.0 for _ in texts]
                    for item in results:
                        try:
                            idx = int(item.get("index", 0))
                            sc = float(item.get("score") or item.get("relevance_score") or 0.0)
                            if 0 <= idx < len(scores):
                                scores[idx] = sc
                        except Exception:
                            continue
                # 归一化到 0..1
                if not scores:
                    return [0.0 for _ in texts]
                mn, mx = min(scores), max(scores)
                if mx - mn < 1e-9:
                    return [0.5 for _ in texts]
                return [(float(s) - mn) / (mx - mn) for s in scores]

        # 简单重试 + 线性退避
        delay_ms = 200
        for i in range(3):
            try:
                return _call()
            except Exception:
                if i == 2:
                    break
                time.sleep(delay_ms / 1000)
                delay_ms *= 2
        return [0.0 for _ in texts]
