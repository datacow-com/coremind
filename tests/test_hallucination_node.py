import asyncio
from core.nodes.hallucination import hallucination


def test_hallucination_low_when_answer_in_context():
    state = {
        "answer": "LangGraph orchestrates RAG.",
        "retrieved_chunks": [
            {"id": "a", "content": "LangGraph orchestrates RAG.", "score": 1.0, "rerank_score": 1.0}
        ]
    }
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(hallucination(state))
    assert 0.0 <= res["hallucination_score"] <= 1.0


def test_hallucination_medium_when_no_context():
    state = {"answer": "foo", "retrieved_chunks": []}
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(hallucination(state))
    assert 0.0 <= res["hallucination_score"] <= 1.0

