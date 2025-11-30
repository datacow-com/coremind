import asyncio
from core.tools.web_search_provider import choose_provider


async def _run():
    p = choose_provider()
    res = await p.search("OmniRAG 测试", max_results=3)
    return res


def test_web_search_runs():
    res = asyncio.run(_run())
    assert isinstance(res, list)
