"""
Shared fixtures for ingestion tests.

Provides common test fixtures used across multiple test modules.
"""

import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import numpy as np


# =============================================================================
# State Fixtures
# =============================================================================

@pytest.fixture
def sample_ingest_state() -> Dict[str, Any]:
    """Sample IngestState for testing."""
    return {
        "channel_id": f"test_ch_{uuid.uuid4().hex[:8]}",
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "file_path": "test/document.pdf",
        "file_type": "pdf",
        "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": {
            "chunking_mode": "fixed",
            "chunk_size": 500,
            "chunk_overlap": 50,
            "enable_cleaning": True,
            "min_quality_score": 0.3,
            "enable_dedup": True,
            "enable_pii_filter": False,
            "embedding_model": "BAAI/bge-m3",
            "embedding_batch_size": 10,
            "embedding_concurrency": 3,
            "embedding_dimensions": 768,
            "vector_backend": "auto",
            "keyword_backend": "elasticsearch",
            "enable_multimodal_index": True,
            "enable_quantization": True,
            "index_batch_size": 100,
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
        "lazy_load": False,
        "local_temp_path": None,
        "file_size": 0,
    }


@pytest.fixture
def base_state(sample_ingest_state) -> Dict[str, Any]:
    """Alias for sample_ingest_state for backward compatibility."""
    return sample_ingest_state


@pytest.fixture
def chunker_base_state() -> Dict[str, Any]:
    """Base state specifically for chunker tests with proper chunking config."""
    return {
        "channel_id": "test_channel",
        "task_id": "task_001",
        "batch_id": "batch_001",
        "file_type": "pdf",
        "strategy_config": {
            "chunking": {
                "mode": "fixed",
                "chunk_size": 100,
                "chunk_overlap": 20,
            }
        },
        "parsed_blocks": [
            {
                "type": "text",
                "content": "This is a sample text block for testing chunking functionality.",
                "page": 1,
                "bbox": [10, 10, 100, 50],
            },
            {
                "type": "table",
                "content": "| Name | Age |\n| --- | --- |\n| Alice | 25 |",
                "page": 1,
                "bbox": [10, 60, 100, 100],
            },
        ],
        "error_log": [],
        "progress": {},
    }


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_blob_store():
    """Mock blob store with configurable behavior."""
    store = AsyncMock()
    store.exists = AsyncMock(return_value=True)
    store.get = AsyncMock(return_value=b"fake_content")
    store.head = AsyncMock(return_value={"size": 1024})
    store.download_to_file = AsyncMock()
    store.stream = AsyncMock()
    return store


@pytest.fixture
def mock_vector_client():
    """Mock Qdrant vector client."""
    client = AsyncMock()
    client.ensure_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.collection_exists = AsyncMock(return_value=True)
    client.get_collection = AsyncMock(return_value=MagicMock(points_count=10))
    return client


@pytest.fixture
def mock_keyword_client():
    """Mock Elasticsearch keyword client."""
    client = AsyncMock()
    client.ensure_index = AsyncMock()
    client.bulk_upsert = AsyncMock()
    client.count = AsyncMock(return_value={"count": 10})
    return client


@pytest.fixture
def mock_embedder():
    """Mock embedder that returns fake vectors."""
    embedder = MagicMock()
    
    def fake_embed_batch(texts):
        return np.random.rand(len(texts), 768).astype(np.float32)
    
    async def async_embed_batch(texts):
        return np.random.rand(len(texts), 768).astype(np.float32)
    
    embedder.embed_batch = fake_embed_batch
    embedder._ensure_config = AsyncMock()
    
    return embedder


@pytest.fixture
def mock_async_embedder():
    """Mock async embedder."""
    embedder = AsyncMock()
    
    async def async_embed_batch(texts):
        return np.random.rand(len(texts), 768).astype(np.float32)
    
    embedder.embed_batch = async_embed_batch
    embedder._ensure_config = AsyncMock()
    
    return embedder


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_parsed_blocks():
    """Sample parsed blocks for testing."""
    return [
        {
            "type": "text",
            "content": "This is the first paragraph with some content.",
            "page": 1,
            "bbox": [10, 10, 200, 50],
        },
        {
            "type": "table",
            "content": "| Name | Age |\n| --- | --- |\n| Alice | 25 |",
            "page": 1,
            "bbox": [10, 60, 200, 120],
        },
        {
            "type": "text",
            "content": "This is the second paragraph after the table.",
            "page": 2,
            "bbox": [10, 10, 200, 50],
        },
        {
            "type": "image",
            "content": "Image description or caption",
            "page": 2,
            "bbox": [10, 60, 200, 160],
        },
    ]


@pytest.fixture
def sample_blocks():
    """Sample blocks for chunker tests (alias for sample_parsed_blocks with image caption)."""
    return [
        {
            "type": "text",
            "content": "This is the first paragraph with some content that should be chunked properly.",
            "page": 1,
            "bbox": [10, 10, 200, 50],
        },
        {
            "type": "table",
            "content": "| Product | Price | Stock |\n| --- | --- | --- |\n| Apple | $1.00 | 100 |\n| Orange | $1.50 | 50 |",
            "page": 1,
            "bbox": [10, 60, 200, 120],
        },
        {
            "type": "text",
            "content": "This is the second paragraph that continues after the table.",
            "page": 2,
            "bbox": [10, 10, 200, 50],
        },
        {
            "type": "image",
            "content": "Image description or caption text",
            "page": 2,
            "bbox": [10, 60, 200, 160],
        },
    ]


@pytest.fixture
def sample_chunks():
    """Sample chunks for testing."""
    return [
        {
            "id": "chunk_001",
            "content": "This is test content for chunk 1.",
            "doc_id": "task_001",
            "chunk_index": 0,
            "metadata": {
                "block_type": "text",
                "page_num": 1,
                "bbox": [10, 10, 100, 50],
                "quality_score": 0.85,
                "language": "en",
            },
        },
        {
            "id": "chunk_002",
            "content": "This is test content for chunk 2.",
            "doc_id": "task_001",
            "chunk_index": 1,
            "metadata": {
                "block_type": "text",
                "page_num": 1,
                "bbox": [10, 60, 100, 100],
                "quality_score": 0.90,
                "language": "en",
            },
        },
    ]


@pytest.fixture
def sample_vectors():
    """Sample embedding vectors for testing."""
    return [
        [0.1] * 768,
        [0.2] * 768,
    ]


@pytest.fixture
def sample_images():
    """Sample image data for testing."""
    return [
        {
            "data": b"fake_image_data_1",
            "page": 1,
            "bbox": [10, 60, 100, 160],
            "caption": "Test image 1",
        },
        {
            "data": b"fake_image_data_2",
            "page": 2,
            "bbox": [10, 60, 100, 160],
            "caption": "Test image 2",
        },
    ]


# =============================================================================
# Test Channel Fixtures
# =============================================================================

@pytest.fixture
def test_channel_a() -> str:
    """Generate unique channel ID for tenant A."""
    return f"test_ch_a_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_channel_b() -> str:
    """Generate unique channel ID for tenant B."""
    return f"test_ch_b_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Path Fixtures
# =============================================================================

@pytest.fixture
def test_docs_dir() -> Path:
    """Path to test documents directory."""
    return Path(__file__).parent.parent / "docs"


@pytest.fixture
def uploads_tmp_dir(tmp_path) -> Path:
    """Temporary uploads directory for testing."""
    uploads_dir = tmp_path / "uploads" / "tmp"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


# =============================================================================
# Error State Fixtures
# =============================================================================

@pytest.fixture
def state_with_errors(sample_ingest_state) -> Dict[str, Any]:
    """State with error log entries."""
    sample_ingest_state["error_log"] = [
        {"stage": "loader", "error": "Connection timeout"},
        {"stage": "parser", "error": "Parse failed"},
    ]
    sample_ingest_state["retry_count"] = 1
    return sample_ingest_state


@pytest.fixture
def state_with_indexer_error(sample_ingest_state) -> Dict[str, Any]:
    """State with indexer-specific error."""
    sample_ingest_state["error_log"] = [
        {"stage": "indexer", "error": "Vector upsert failed"},
    ]
    sample_ingest_state["retry_count"] = 1
    return sample_ingest_state


# =============================================================================
# Quality Check Fixtures
# =============================================================================

@pytest.fixture
def state_with_low_quality_chunks(sample_ingest_state) -> Dict[str, Any]:
    """State with low quality chunks."""
    sample_ingest_state["chunks"] = [
        {"id": "bad_1", "content": "x", "metadata": {}},
        {"id": "bad_2", "content": "!!!", "metadata": {}},
    ]
    return sample_ingest_state


@pytest.fixture
def state_with_duplicate_chunks(sample_ingest_state) -> Dict[str, Any]:
    """State with duplicate chunks."""
    duplicate_content = "This is duplicate content that appears multiple times."
    sample_ingest_state["chunks"] = [
        {"id": "chunk_1", "content": duplicate_content, "metadata": {}},
        {"id": "chunk_2", "content": duplicate_content, "metadata": {}},
        {"id": "chunk_3", "content": "Unique content here.", "metadata": {}},
    ]
    return sample_ingest_state


# =============================================================================
# Autouse Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset all singleton clients before and after each test.
    
    Prevents "Event loop is closed" errors when using async clients
    across different pytest-asyncio event loops.
    """
    def _reset_all():
        try:
            from server.database import reset_engine_force
            reset_engine_force()
        except (ImportError, AttributeError):
            pass
        
        try:
            from core.storage.vector_store import reset_vector_client
            reset_vector_client()
        except (ImportError, AttributeError):
            pass
        
        try:
            from core.storage.keyword_store import reset_keyword_client
            reset_keyword_client()
        except (ImportError, AttributeError):
            pass
    
    _reset_all()
    yield
    _reset_all()
