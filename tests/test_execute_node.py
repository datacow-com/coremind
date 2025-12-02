import asyncio


def test_execute_exports_tables():
    from core.nodes.execute import execute

    chunks = [
        {
            "id": "t1",
            "content": "| a | b |\n| --- | --- |\n| 1 | 2 |",
            "page_num": 1,
            "doc_id": "doc.pdf",
            "chunk_index": 0,
            "metadata": {"type": "table", "bbox": [0, 0, 10, 10]},
            "score": 0.9,
            "rerank_score": None,
        },
    ]
    state = {"intent": "execute", "retrieved_chunks": chunks}
    res = asyncio.run(execute(state))
    ans = res.get("answer") or ""
    assert "1,2" in ans
