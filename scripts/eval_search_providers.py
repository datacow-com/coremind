import asyncio
import time
from core.tools.web_search_provider import choose_provider


async def run(query: str, max_results: int = 5):
    p = choose_provider()
    t0 = time.perf_counter()
    results = await p.search(query, max_results=max_results)
    dur = int((time.perf_counter() - t0) * 1000)
    out = [{"title": r.get("title"), "url": r.get("url")} for r in results]
    print({"duration_ms": dur, "count": len(out), "results": out})


if __name__ == "__main__":
    asyncio.run(run("LangGraph 状态机 编排 原理", max_results=5))
