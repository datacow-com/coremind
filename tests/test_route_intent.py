import asyncio


def test_route_intent_classification():
    from core.nodes.route import route

    async def run(q):
        return await route({"query": q})

    res1 = asyncio.run(run("请总结一下这份报告"))
    res2 = asyncio.run(run("联网搜索一下最近的新闻"))
    res3 = asyncio.run(run("执行一个导出任务"))
    res4 = asyncio.run(run("普通问答"))
    assert res1.get("intent") == "summarize"
    assert res2.get("intent") == "web_search"
    assert res3.get("intent") == "execute"
    assert res4.get("intent") == "qa"
