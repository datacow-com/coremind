import asyncio
import os
import time
from collections.abc import Callable
from typing import TypeVar

from core.tools.config_store import load_web_search_configs
from server.config import settings

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

T = TypeVar("T")


class _BaseSearch:
    def __init__(self, timeout: float = 8.0, name: str = "unknown"):
        self.timeout = timeout
        self.name = name
        self._cb_state: list[float] = []
        self._cb_cooldown: float | None = None
        if prometheus_client:
            self._metric_latency = prometheus_client.Histogram(
                "web_search_duration_ms",
                "Web search duration (ms)",
                ["provider"],
                buckets=(50, 100, 200, 500, 1000, 2000, 5000, 10000),
            )
            self._metric_errors = prometheus_client.Counter(
                "web_search_errors", "Web search errors", ["provider"]
            )
        else:
            self._metric_latency = None
            self._metric_errors = None

    def _record(self, dur_ms: float, error: bool = False):
        if self._metric_latency:
            try:
                self._metric_latency.labels(self.name).observe(dur_ms)
            except Exception:
                pass
        if error and self._metric_errors:
            try:
                self._metric_errors.labels(self.name).inc()
            except Exception:
                pass

    async def _with_retry(self, fn: Callable[[], T]) -> T:
        max_fail = int(getattr(settings, "breaker_max_failures", 3) or 3)
        window = float(getattr(settings, "breaker_window_seconds", 60) or 60)
        cooldown = float(getattr(settings, "breaker_cooldown_seconds", 30) or 30)
        attempts = int(getattr(settings, "llm_retry_attempts", 2) or 2)
        backoff = float(getattr(settings, "llm_retry_backoff_ms", 500) or 500) / 1000.0

        now = time.time()
        if self._cb_cooldown and now < self._cb_cooldown:
            return []

        def on_fail():
            nonlocal now
            now = time.time()
            fails = [t for t in self._cb_state if now - t <= window]
            fails.append(now)
            self._cb_state = fails
            if len(fails) >= max_fail:
                self._cb_cooldown = now + cooldown

        def on_success():
            self._cb_state = []
            self._cb_cooldown = None

        last = None
        for i in range(attempts + 1):
            t0 = time.perf_counter()
            try:
                out = await fn()
                self._record((time.perf_counter() - t0) * 1000)
                on_success()
                return out
            except Exception as e:
                last = e
                self._record((time.perf_counter() - t0) * 1000, error=True)
                on_fail()
                if i >= attempts:
                    return []
                await asyncio.sleep(backoff * (2**i))
        return []


class SimpleWebSearch(_BaseSearch):
    def __init__(self, timeout: float = 8.0, base_url: str | None = None):
        super().__init__(timeout=timeout, name="duckduckgo")
        self.base_url = base_url or "https://duckduckgo.com/html/"
        # 默认 UA 以降低反爬概率
        self.headers = {
            "User-Agent": os.environ.get(
                "WEBSEARCH_UA",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            )
        }

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        try:
            import httpx
            from selectolax.parser import HTMLParser  # more robust parser
        except Exception:
            return []
        params = {"q": query}

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as http:
                r = await http.get(self.base_url, params=params)
                r.raise_for_status()
                html = r.text
                tree = HTMLParser(html)
                out: list[dict[str, str]] = []
                for a in tree.css("a.result__a")[:max_results]:
                    href = a.attributes.get("href") or ""
                    title = a.text(strip=True)
                    out.append({"url": href, "title": title})
                return out

        return await self._with_retry(_call)


class TavilySearch(_BaseSearch):
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        cfgs = load_web_search_configs()
        cfg = next((c for c in cfgs if c.get("name") == "tavily"), None)
        self.api_key = (
            api_key or (cfg.get("api_key") if cfg else None) or os.environ.get("TAVILY_API_KEY")
        )
        super().__init__(
            timeout=timeout if api_key else float((cfg or {}).get("timeout") or timeout),
            name="tavily",
        )

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        payload = {"api_key": self.api_key, "query": query, "max_results": max_results}

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post("https://api.tavily.com/search", json=payload)
                r.raise_for_status()
                data = r.json()
                out: list[dict[str, str]] = []
                for item in data.get("results", [])[:max_results]:
                    out.append(
                        {
                            "url": item.get("url"),
                            "title": item.get("title"),
                            "snippet": item.get("content"),
                        }
                    )
                return out

        return await self._with_retry(_call)


class SerperSearch(_BaseSearch):
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        cfgs = load_web_search_configs()
        cfg = next((c for c in cfgs if c.get("name") == "serper"), None)
        self.api_key = (
            api_key or (cfg.get("api_key") if cfg else None) or os.environ.get("SERPER_API_KEY")
        )
        super().__init__(
            timeout=timeout if api_key else float((cfg or {}).get("timeout") or timeout),
            name="serper",
        )

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query}

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post(
                    "https://google.serper.dev/search", headers=headers, json=payload
                )
                r.raise_for_status()
                data = r.json()
                out: list[dict[str, str]] = []
                for item in (data.get("organic") or [])[:max_results]:
                    out.append(
                        {
                            "url": item.get("link"),
                            "title": item.get("title"),
                            "snippet": item.get("snippet"),
                        }
                    )
                return out

        return await self._with_retry(_call)


class BochaSearch(_BaseSearch):
    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ):
        cfgs = load_web_search_configs()
        cfg = next((c for c in cfgs if c.get("name") == "bocha"), None)
        self.api_key = (
            api_key
            or (cfg.get("api_key") if cfg else None)
            or os.environ.get("BOCHA_WEB_SEARCH_API_KEY")
        )
        self.base_url = (
            base_url
            or (cfg.get("base_url") if cfg else None)
            or os.environ.get("BOCHA_BASE_URL")
            or "https://api.bochaai.com/v1/ai-search"
        )
        super().__init__(
            timeout=timeout if api_key else float((cfg or {}).get("timeout") or timeout),
            name="bocha",
        )

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"q": query, "top_k": max_results}

        async def _call():
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post(self.base_url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json() or {}
                items = (data.get("webPages") or {}).get("value") or []
                out: list[dict[str, str]] = []
                for item in items[:max_results]:
                    out.append(
                        {
                            "url": item.get("url"),
                            "title": item.get("name"),
                            "snippet": item.get("snippet"),
                        }
                    )
                return out

        return await self._with_retry(_call)


def simple_overlap_score(query: str, text: str) -> float:
    q = set([w for w in (query or "").lower().split() if w])
    T = set([w for w in (text or "").lower().split() if w])
    if not q:
        return 0.0
    return len(q & T) / len(q)
