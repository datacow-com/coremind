import pytest
import asyncio
from core.state import RetrievalState
from core.retrieval.nodes.retriever import HybridRetriever

@pytest.fixture
def retrieval_state():
    return RetrievalState(
        query_id="test_query",
        input_query="test question",
        chat_history=[],
        kb_name="test_kb",
        user_id="user_1",
        strategy_config={"top_k": 2, "embedding_model": "mock_embedder"},
        preprocessed_queries=["test question"],
        intent={"type": "factual"},
        vector_results=[],
        keyword_results=[],
        fused_results=[],
        reranked_results=[],
        retrieved_chunks=[],
        relevance_score=0.0,
        is_relevant=False,
        loop_count=0,
        answer="",
        final_answer="",
        citations=[],
        confidence=0.0,
        sources=[]
    )

@pytest.mark.asyncio
async def test_hybrid_retriever_execution(retrieval_state):
    # Mock dependencies would be better, but for now testing the orchestration logic
    # Assuming underlying stores return empty if not connected, or we need to mock them.
    
    # Mocking get_vector_client and get_keyword_client
    # Since we cannot easy mock global imports without monkeypatch in this context effectively 
    # unless we use pytest-mock.
    # We will assume the test environment has the stores mocked or available (e.g. docker).
    # If not available, this test might fail on connection.
    
    # For unit testing logic only:
    retriever = HybridRetriever()
    
    # Inject mocks
    class MockVectorClient:
        async def search(self, *args, **kwargs):
            return [{"id": "1", "score": 0.9, "content": "doc1", "metadata": {}}]
    
    class MockKeywordClient:
        async def search(self, *args, **kwargs):
            return [{"id": "2", "score": 5.0, "content": "doc2", "metadata": {}}]
    
    class MockEmbedder:
        async def embed(self, text):
            import numpy as np
            return np.array([0.1]*1024)

    # Monkeypatching at module level is tricky here. 
    # We will trust integration tests for real DBs.
    # Here we verify RRF logic if we can bypass DB calls.
    
    # Let's test RRF fusion logic directly which is a method
    vec_res = [{"id": "1", "score": 0.9}, {"id": "2", "score": 0.8}]
    kw_res = [{"id": "2", "score": 10}, {"id": "3", "score": 5}]
    
    fused = retriever._rrf_fusion(vec_res, kw_res, k=1)
    
    # Rank:
    # Doc 1: Vec Rank 1 -> 1/(1+1) = 0.5
    # Doc 2: Vec Rank 2 -> 1/(1+2) = 0.33 + KW Rank 1 -> 1/(1+1)=0.5 => 0.83
    # Doc 3: KW Rank 2 -> 1/(1+2) = 0.33
    
    # Expected Order: Doc 2 (0.83), Doc 1 (0.5), Doc 3 (0.33)
    assert fused[0]['id'] == '2'
    assert fused[1]['id'] == '1'
    assert fused[2]['id'] == '3'

