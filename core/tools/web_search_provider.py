from typing import List, Dict, Optional
import os


class SimpleWebSearch:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        try:
            import httpx
            import re
        except Exception:
            return []
        url = "https://duckduckgo.com/html/"
        params = {"q": query}
        out: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.get(url, params=params)
                if r.status_code != 200:
                    return []
                html = r.text
                links = re.findall(r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>', html, flags=re.IGNORECASE)
                for href, title in links[:max_results]:
                    clean_title = re.sub(r"<[^>]+>", "", title)
                    out.append({"url": href, "title": clean_title})
        except Exception:
            return []
        return out


class TavilySearch:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        payload = {"api_key": self.api_key, "query": query, "max_results": max_results}
        out: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post("https://api.tavily.com/search", json=payload)
                if r.status_code != 200:
                    return []
                data = r.json()
                for item in data.get("results", [])[:max_results]:
                    out.append({"url": item.get("url"), "title": item.get("title"), "snippet": item.get("content")})
        except Exception:
            return []
        return out


class SerperSearch:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 8.0):
        self.api_key = api_key or os.environ.get("SERPER_API_KEY")
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        if not self.api_key:
            return []
        try:
            import httpx
        except Exception:
            return []
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        payload = {"q": query}
        out: List[Dict[str, str]] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post("https://google.serper.dev/search", headers=headers, json=payload)
                if r.status_code != 200:
                    return []
                data = r.json()
                for item in (data.get("organic") or [])[:max_results]:
                    out.append({"url": item.get("link"), "title": item.get("title"), "snippet": item.get("snippet")})
        except Exception:
            return []
        return out


def choose_provider():
    if os.environ.get("TAVILY_API_KEY"):
        return TavilySearch()
    if os.environ.get("SERPER_API_KEY"):
        return SerperSearch()
    return SimpleWebSearch()


def simple_overlap_score(query: str, text: str) -> float:
    q = set([w for w in (query or "").lower().split() if w])
    T = set([w for w in (text or "").lower().split() if w])
    if not q:
        return 0.0
    return len(q & T) / len(q)
