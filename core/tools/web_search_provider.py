from typing import List, Dict


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
