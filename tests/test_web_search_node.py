import asyncio

from core.nodes.web_search import web_search


def test_web_search_returns_list_even_without_keys():
    state = {"query": "LangGraph"}
    res = asyncio.run(web_search(state))
    assert "retrieved_chunks" in res
    assert isinstance(res["retrieved_chunks"], list)
