import asyncio
import os
import time

from server.config import settings


class SimpleWebSearch:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._cb_state: list[float] = []
        self._cb_cooldown: float | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        try:
            import re

            import httpx
        except Exception:
            return []
        url = "https://duckduckgo.com/html/"
        params = {"q": query}
        out: list[dict[str, str]] = []
        now = time.time()
        max_fail = int(getattr(settings, "breaker_max_failures", 3) or 3)
        window = float(getattr(settings, "breaker_window_seconds", 60) or 60)
        cooldown = float(getattr(settings, "breaker_cooldown_seconds", 30) or 30)
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

        attempts = int(getattr(settings, "llm_retry_attempts", 2) or 2)
        backoff = float(getattr(settings, "llm_retry_backoff_ms", 500) or 500) / 1000.0
        for i in range(attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as http:
                    r = await http.get(url, params=params)
                    if r.status_code != 200:
                        raise RuntimeError("http error")
                    html = r.text
                    links = re.findall(
                        r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
                        html,
                        flags=re.IGNORECASE,
                    )
                    for href, title in links[:max_results]:
                        clean_title = re.sub(r"<[^>]+>", "", title)
                        out.append({"url": href, "title": clean_title})
                    return out
            except Exception:
                on_fail()
                if i >= attempts:
                    return []
                await asyncio.sleep(backoff * (2**i))
            else:
                on_success()
                return out
        return out


class TavilySearch:
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.timeout = timeout
        self._cb_state: list[float] = []
        self._cb_cooldown: float | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        payload = {"api_key": self.api_key, "query": query, "max_results": max_results}
        out: list[dict[str, str]] = []
        now = time.time()
        max_fail = int(getattr(settings, "breaker_max_failures", 3) or 3)
        window = float(getattr(settings, "breaker_window_seconds", 60) or 60)
        cooldown = float(getattr(settings, "breaker_cooldown_seconds", 30) or 30)
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

        attempts = int(getattr(settings, "llm_retry_attempts", 2) or 2)
        backoff = float(getattr(settings, "llm_retry_backoff_ms", 500) or 500) / 1000.0
        for i in range(attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as http:
                    r = await http.post("https://api.tavily.com/search", json=payload)
                    if r.status_code != 200:
                        raise RuntimeError("http error")
                    data = r.json()
                    for item in data.get("results", [])[:max_results]:
                        out.append(
                            {
                                "url": item.get("url"),
                                "title": item.get("title"),
                                "snippet": item.get("content"),
                            }
                        )
                    return out
            except Exception:
                on_fail()
                if i >= attempts:
                    return []
                await asyncio.sleep(backoff * (2**i))
            else:
                on_success()
                return out
        return out


class SerperSearch:
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        self.timeout = timeout
        self._cb_state: list[float] = []
        self._cb_cooldown: float | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query}
        out: list[dict[str, str]] = []
        now = time.time()
        max_fail = int(getattr(settings, "breaker_max_failures", 3) or 3)
        window = float(getattr(settings, "breaker_window_seconds", 60) or 60)
        cooldown = float(getattr(settings, "breaker_cooldown_seconds", 30) or 30)
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

        attempts = int(getattr(settings, "llm_retry_attempts", 2) or 2)
        backoff = float(getattr(settings, "llm_retry_backoff_ms", 500) or 500) / 1000.0
        for i in range(attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as http:
                    r = await http.post(
                        "https://google.serper.dev/search", headers=headers, json=payload
                    )
                    if r.status_code != 200:
                        raise RuntimeError("http error")
                    data = r.json()
                    for item in (data.get("organic") or [])[:max_results]:
                        out.append(
                            {
                                "url": item.get("link"),
                                "title": item.get("title"),
                                "snippet": item.get("snippet"),
                            }
                        )
                    return out
            except Exception:
                on_fail()
                if i >= attempts:
                    return []
                await asyncio.sleep(backoff * (2**i))
            else:
                on_success()
                return out
        return out


class BochaSearch:
    def __init__(
        self, api_key: str | None = None, base_url: str | None = None, timeout: float = 8.0
    ):
        self.api_key = api_key or os.environ.get("BOCHA_WEB_SEARCH_API_KEY")
        self.base_url = (
            base_url or os.environ.get("BOCHA_BASE_URL") or "https://api.bochaai.com/v1/ai-search"
        )
        self.timeout = timeout
        self._cb_state: list[float] = []
        self._cb_cooldown: float | None = None

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        out: list[dict[str, str]] = []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"q": query, "top_k": max_results}
        now = time.time()
        max_fail = int(getattr(settings, "breaker_max_failures", 3) or 3)
        window = float(getattr(settings, "breaker_window_seconds", 60) or 60)
        cooldown = float(getattr(settings, "breaker_cooldown_seconds", 30) or 30)
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

        attempts = int(getattr(settings, "llm_retry_attempts", 2) or 2)
        backoff = float(getattr(settings, "llm_retry_backoff_ms", 500) or 500) / 1000.0
        for i in range(attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as http:
                    r = await http.post(self.base_url, headers=headers, json=payload)
                    if r.status_code != 200:
                        raise RuntimeError("http error")
                    data = r.json() or {}
                    items = (data.get("webPages") or {}).get("value") or []
                    for item in items[:max_results]:
                        out.append(
                            {
                                "url": item.get("url"),
                                "title": item.get("name"),
                                "snippet": item.get("snippet"),
                            }
                        )
                    return out
            except Exception:
                on_fail()
                if i >= attempts:
                    return []
                await asyncio.sleep(backoff * (2**i))
            else:
                on_success()
                return out
        return out


def simple_overlap_score(query: str, text: str) -> float:
    q = set([w for w in (query or "").lower().split() if w])
    T = set([w for w in (text or "").lower().split() if w])
    if not q:
        return 0.0
    return len(q & T) / len(q)
