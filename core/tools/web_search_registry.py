import os

from core.tools.config_store import load_web_search_configs
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
    cfgs = load_web_search_configs()
    # Named selection
    if nm == "bocha":
        return BochaSearch(timeout=to or 8.0)
    if nm == "tavily":
        return TavilySearch(timeout=to or 8.0)
    if nm == "serper":
        return SerperSearch(timeout=to or 8.0)
    if nm in {"duckduckgo", "ddg", "simple"}:
        return SimpleWebSearch(timeout=to or 8.0)
    # Auto: pick first enabled by priority (DB)，否则回退 env
    if cfgs:
        for c in cfgs:
            n = (c.get("name") or "").lower()
            if n == "tavily":
                return TavilySearch(timeout=to or float(c.get("timeout") or 8.0))
            if n == "serper":
                return SerperSearch(timeout=to or float(c.get("timeout") or 8.0))
            if n == "bocha":
                return BochaSearch(timeout=to or float(c.get("timeout") or 8.0))
            if n in {"duckduckgo", "ddg", "simple"}:
                return SimpleWebSearch(timeout=to or float(c.get("timeout") or 8.0))
    # Env fallback
    if os.environ.get("TAVILY_API_KEY"):
        return TavilySearch(timeout=to or 8.0)
    if os.environ.get("SERPER_API_KEY"):
        return SerperSearch(timeout=to or 8.0)
    if os.environ.get("BOCHA_WEB_SEARCH_API_KEY") or os.environ.get("BOCHA_BASE_URL"):
        return BochaSearch(timeout=to or 8.0)
    return SimpleWebSearch(timeout=to or 8.0)
