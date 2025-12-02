import os

from server.config import settings


class SimpleWebSearch:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        try:
            import re

            import httpx
        except Exception:
            return []
        url = "https://duckduckgo.com/html/"
        params = {"q": query}
        out: list[dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.get(url, params=params)
                if r.status_code != 200:
                    return []
                html = r.text
                links = re.findall(
                    r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
                    html,
                    flags=re.IGNORECASE,
                )
                for href, title in links[:max_results]:
                    clean_title = re.sub(r"<[^>]+>", "", title)
                    out.append({"url": href, "title": clean_title})
        except Exception:
            return []
        return out


class TavilySearch:
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        payload = {"api_key": self.api_key, "query": query, "max_results": max_results}
        out: list[dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post("https://api.tavily.com/search", json=payload)
                if r.status_code != 200:
                    return []
                data = r.json()
                for item in data.get("results", [])[:max_results]:
                    out.append(
                        {
                            "url": item.get("url"),
                            "title": item.get("title"),
                            "snippet": item.get("content"),
                        }
                    )
        except Exception:
            return []
        return out


class SerperSearch:
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        self.timeout = timeout

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
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post(
                    "https://google.serper.dev/search", headers=headers, json=payload
                )
                if r.status_code != 200:
                    return []
                data = r.json()
                for item in (data.get("organic") or [])[:max_results]:
                    out.append(
                        {
                            "url": item.get("link"),
                            "title": item.get("title"),
                            "snippet": item.get("snippet"),
                        }
                    )
        except Exception:
            return []
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
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post(self.base_url, headers=headers, json=payload)
                if r.status_code != 200:
                    return []
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
        except Exception:
            return []
        return out


def choose_provider():
    p = (settings.web_search_provider or "").lower()
    timeout = float(getattr(settings, "web_search_timeout", 8.0))
    if p == "bocha" and (
        os.environ.get("BOCHA_WEB_SEARCH_API_KEY") or os.environ.get("BOCHA_BASE_URL")
    ):
        return BochaSearch(timeout=timeout)
    if p == "tavily" and (os.environ.get("TAVILY_API_KEY")):
        return TavilySearch(timeout=timeout)
    if p == "serper" and (os.environ.get("SERPER_API_KEY")):
        return SerperSearch(timeout=timeout)
    # env fallback
    if os.environ.get("BOCHA_WEB_SEARCH_API_KEY") or os.environ.get("BOCHA_BASE_URL"):
        return BochaSearch(timeout=timeout)
    if os.environ.get("TAVILY_API_KEY"):
        return TavilySearch(timeout=timeout)
    if os.environ.get("SERPER_API_KEY"):
        return SerperSearch(timeout=timeout)
    return SimpleWebSearch(timeout=timeout)


def simple_overlap_score(query: str, text: str) -> float:
    q = set([w for w in (query or "").lower().split() if w])
    T = set([w for w in (text or "").lower().split() if w])
    if not q:
        return 0.0
    return len(q & T) / len(q)
