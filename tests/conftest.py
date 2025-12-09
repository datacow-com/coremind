"""Shared pytest fixtures for core tests."""

from typing import Any

import pytest


@pytest.fixture
def sample_chunk_metadata() -> dict[str, Any]:
    """Sample chunk metadata for testing."""
    return {
        "channel_id": "test_channel",
        "doc_id": "doc_001",
        "batch_id": "batch_001",
        "page_num": 1,
        "bbox": [0, 0, 100, 100],
        "block_type": "text",
        "media_type": "application/pdf",
        "language": "zh",
        "quality_score": 0.95,
        "ocr_provider": None,
        "ocr_confidence": None,
    }


@pytest.fixture
def sample_ingest_state() -> dict[str, Any]:
    """Sample ingest state for testing."""
    return {
        "channel_id": "test_channel",
        "task_id": "task_001",
        "file_path": "test/doc.pdf",
        "file_type": "pdf",
        "batch_id": "batch_001",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": {
            "ocr_provider": "auto",
            "chunking": {"mode": "fixed", "chunk_size": 512},
            "embedding_model": "BAAI/bge-m3",
        },
        "capability_loader": None,
        "raw_content": None,
        "extracted_text": None,
        "parsed_blocks": [],
        "images": [],
        "chunks": [],
        "vectors": [],
        "processing_stage": "upload",
        "retry_count": 0,
        "error_log": [],
        "progress": {},
        "quality_metrics": {},
    }


@pytest.fixture
def sample_retrieval_state() -> dict[str, Any]:
    """Sample retrieval state for testing."""
    return {
        "channel_id": "test_channel",
        "session_id": "session_001",
        "query_id": "query_001",
        "input_query": "What is the capital of France?",
        "chat_history": [],
        "kb_names": ["test_kb"],
        "user_id": "user_001",
        "strategy_config": {
            "top_k": 5,
            "rerank_threshold": 0.0,
            "embedding_model": "BAAI/bge-m3",
        },
        "capability_loader": None,
        "preprocessed_queries": [],
        "intent": {},
        "vector_results": [],
        "keyword_results": [],
        "fused_results": [],
        "reranked_results": [],
        "retrieved_chunks": [],
        "relevance_score": 0.0,
        "is_relevant": False,
        "loop_count": 0,
        "answer": "",
        "final_answer": "",
        "citations": [],
        "confidence": 0.0,
        "sources": [],
    }
