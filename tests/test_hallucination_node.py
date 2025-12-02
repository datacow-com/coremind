import asyncio

from core.nodes.hallucination import hallucination


async def _run():
    state = {
        "answer": "这是一个回答",
        "retrieved_chunks": [
            {
                "id": "x",
                "content": "上下文 文本",
                "page_num": 1,
                "doc_id": "doc",
                "chunk_index": 0,
                "metadata": {},
                "score": 0.5,
                "rerank_score": None,
            }
        ],
    }
    return await hallucination(state)


def test_hallucination_outputs_score():
    out = asyncio.run(_run())
    assert "hallucination_score" in out
    assert "hallucination_detected" in out
