import asyncio
import time
from core.graph import create_graph


async def one(app, q):
    t0 = time.perf_counter()
    ans = None
    async for up in app.astream({"query": q, "metadata": {"top_k": 5}}):
        if up.get("answer"):
            ans = up.get("answer")
    return int((time.perf_counter() - t0) * 1000), len(ans or "")


async def main(concurrency: int = 10):
    app = create_graph()
    qs = [f"测试并发 {i}" for i in range(concurrency)]
    t0 = time.perf_counter()
    res = await asyncio.gather(*[one(app, q) for q in qs])
    dur = int((time.perf_counter() - t0) * 1000)
    avg = sum([r[0] for r in res]) / max(len(res), 1)
    print({"total_ms": dur, "avg_ms": avg, "count": len(res)})


if __name__ == "__main__":
    asyncio.run(main(concurrency=10))
