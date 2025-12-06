from core.tools.web_search_provider import (
    BochaSearch,
    SerperSearch,
    SimpleWebSearch,
    TavilySearch,
)


def get_web_search_provider(name: str | None = None, timeout: float | None = None):
    """
    Registry for web search providers.

    name: bocha | tavily | serper | duckduckgo(simple) | auto/None
    timeout: override per-call timeout
    """
    nm = (name or "").lower()
    to = timeout if timeout is not None else None
    if nm == "bocha":
        return BochaSearch(timeout=to or 8.0)
    if nm == "tavily":
        return TavilySearch(timeout=to or 8.0)
    if nm == "serper":
        return SerperSearch(timeout=to or 8.0)
    if nm in {"duckduckgo", "ddg", "simple"}:
        return SimpleWebSearch(timeout=to or 8.0)
    # auto fallback: prefer tavily/serper when keys present
    if os.environ.get("TAVILY_API_KEY"):
        return TavilySearch(timeout=to or 8.0)
    if os.environ.get("SERPER_API_KEY"):
        return SerperSearch(timeout=to or 8.0)
    if os.environ.get("BOCHA_WEB_SEARCH_API_KEY") or os.environ.get("BOCHA_BASE_URL"):
        return BochaSearch(timeout=to or 8.0)
    return SimpleWebSearch(timeout=to or 8.0)
