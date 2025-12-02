import asyncio
import os

from core.nodes.rerank import rerank


async def _run():
    os.environ["RERANKER_FILTER_THRESHOLD"] = "0.5"
    state = {
        "query": "测试 关键字",
        "retrieved_chunks": [
            {
                "id": "a",
                "content": "测试 内容",
                "page_num": 1,
                "doc_id": "doc",
                "chunk_index": 0,
                "metadata": {},
                "score": 0.4,
                "rerank_score": None,
            },
            {
                "id": "b",
                "content": "关键字 内容",
                "page_num": 1,
                "doc_id": "doc",
                "chunk_index": 1,
                "metadata": {},
                "score": 0.9,
                "rerank_score": None,
            },
        ],
        "metadata": {"top_k": 8},
    }
    out = await rerank(state)
    return out


def test_rerank_filters_low_scores():
    out = asyncio.run(_run())
    items = out.get("retrieved_chunks") or []
    ids = [it.get("id") for it in items]
    assert "b" in ids
    assert "a" not in ids
