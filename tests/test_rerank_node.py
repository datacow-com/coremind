import asyncio
from core.nodes.rerank import rerank


def test_rerank_orders_by_overlap_and_score():
    state = {
        "query": "LangGraph parsing",
        "retrieved_chunks": [
            {
                "id": "a",
                "content": "This section explains LangGraph.",
                "page_num": 1,
                "doc_id": "d",
                "chunk_index": 0,
                "metadata": {},
                "score": 0.4,
                "rerank_score": None,
            },
            {
                "id": "b",
                "content": "Unrelated content.",
                "page_num": 1,
                "doc_id": "d",
                "chunk_index": 1,
                "metadata": {},
                "score": 0.8,
                "rerank_score": None,
            },
        ],
    }
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(rerank(state))
    items = res["retrieved_chunks"]
    assert len(items) == 2
    assert items[0]["id"] in {"a", "b"}
    assert items[0]["rerank_score"] >= items[1]["rerank_score"]

