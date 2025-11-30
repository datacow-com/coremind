import asyncio
import time
from core.graph import create_graph


async def run(query: str, top_k: int = 5):
    app = create_graph()
    state = {"query": query, "metadata": {"top_k": top_k}}
    t0 = time.perf_counter()
    updates = []
    async for up in app.astream(state):
        updates.append(up)
    dur = int((time.perf_counter() - t0) * 1000)
    answer = ""
    metrics = {}
    for u in updates:
        if u.get("answer"):
            answer = u.get("answer")
        if u.get("metrics"):
            metrics.update(u.get("metrics"))
    print({
        "ttft_ms": dur,
        "metrics": metrics,
        "answer_len": len(answer or ""),
    })


if __name__ == "__main__":
    asyncio.run(run("项目的核心架构是什么？", top_k=8))
