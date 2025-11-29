from core.reranker.cross_encoder import Reranker


def test_cross_encoder_reranker_fallback_and_shape():
    rr = Reranker()
    s = rr.score("LangGraph", ["LangGraph orchestrates RAG.", "Unrelated content."])
    assert len(s) == 2
    assert all(0.0 <= x <= 1.0 for x in s)

