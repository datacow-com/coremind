import asyncio
from core.nodes.grade import grade


def test_grade_sets_web_needed_when_empty():
    state = {"retrieved_chunks": []}
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(grade(state))
    assert res["web_search_needed"] is True


def test_grade_threshold_logic():
    state = {
        "retrieved_chunks": [
            {"id": "a", "content": "x", "score": 0.2, "rerank_score": 0.2},
            {"id": "b", "content": "y", "score": 0.4, "rerank_score": 0.4},
        ]
    }
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(grade(state))
    assert res["web_search_needed"] is False

