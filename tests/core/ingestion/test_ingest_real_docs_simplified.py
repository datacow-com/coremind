"""
Simplified Real E2E tests for ingestion pipeline.

These tests verify the pipeline works with REAL services but use:
1. Small test files (not large PDFs)
2. Simple embedder (not heavy ML models)
3. Reasonable timeouts

For heavy integration testing, use test_ingest_integration.py with mocks.
"""

import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

import pytest

from tests.core.conftest_real import (
    requires_all_services,
    requires_qdrant,
    requires_elasticsearch,
    check_qdrant_available,
    check_elasticsearch_available,
)


# =============================================================================
# Fixture to reset singletons between tests
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset all async client singletons before and after each test.
    
    This prevents "Event loop is closed" errors when using async clients
    across different pytest-asyncio event loops.
    """
    def _reset_all():
        try:
            from server.database import reset_engine_force
            reset_engine_force()
        except ImportError:
            pass
        
        try:
            from core.storage.vector_store import reset_vector_client
            reset_vector_client()
        except ImportError:
            pass
        
        try:
            from core.storage.keyword_store import reset_keyword_client
            reset_keyword_client()
        except ImportError:
            pass
    
    _reset_all()
    yield
    _reset_all()


# =============================================================================
# Test Constants
# =============================================================================

# Use much shorter timeout for simplified tests
TEST_TIMEOUT = 30  # seconds


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def simple_embedder():
    """Simple embedder that returns random vectors quickly."""
    import numpy as np
    
    class SimpleEmbedder:
        def __init__(self):
            self.dim = 256  # Small dimension for speed
        
        def embed_batch(self, texts):
            return np.random.rand(len(texts), self.dim).astype(np.float32)
        
        async def _ensure_config(self):
            pass
    
    return SimpleEmbedder()


@pytest.fixture
def test_channel_id():
    """Generate unique channel ID for test isolation."""
    return f"test_ch_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def small_test_file(tmp_path):
    """Create a small test file for quick testing."""
    content = "This is a test document.\n\n" * 50  # ~1KB
    file_path = tmp_path / "test_doc.txt"
    file_path.write_text(content)
    return file_path


# =============================================================================
# Helper Functions
# =============================================================================

def check_services_available() -> bool:
    """Check if required services (Qdrant, ES) are available."""
    return check_qdrant_available() and check_elasticsearch_available()


async def run_simplified_pipeline(
    file_path: Path,
    channel_id: str,
    simple_embedder,
    strategy_config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Run ingestion pipeline with simplified embedder.
    
    Uses a simple random embedder instead of heavy ML models.
    """
    from core.state import IngestState, StrategyConfig
    from core.ingestion.graph import create_ingest_graph_no_checkpoint
    
    if strategy_config is None:
        strategy_config = {}
    
    # Force small embedding dimension
    strategy_config["embedding_dimensions"] = 256
    
    config = StrategyConfig(**strategy_config)
    
    initial_state: IngestState = {
        "channel_id": channel_id,
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "file_path": str(file_path),
        "file_type": file_path.suffix.lstrip(".").lower(),
        "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": config.model_dump(),
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
    
    # Patch embedder to use simple version
    with patch("core.ingestion.nodes.embedder.get_embedder", return_value=simple_embedder):
        graph = create_ingest_graph_no_checkpoint()
        final_state = await graph.ainvoke(initial_state)
    
    return final_state


# =============================================================================
# Simplified E2E Tests
# =============================================================================

@pytest.mark.real_e2e
class TestSimplifiedE2E:
    """Simplified E2E tests that run quickly."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_text_file_ingestion(
        self,
        test_channel_id: str,
        small_test_file: Path,
        simple_embedder,
    ):
        """Test ingestion of a simple text file."""
        # Skip if services not available
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        result = await run_simplified_pipeline(
            file_path=small_test_file,
            channel_id=test_channel_id,
            simple_embedder=simple_embedder,
        )
        
        # Verify completion
        assert result["processing_stage"] in ("finalize", "completed"), \
            f"Pipeline failed at stage: {result['processing_stage']}"
        
        # Verify chunks created
        assert len(result["chunks"]) > 0, "No chunks created"
        
        # Verify vectors created
        assert len(result["vectors"]) > 0, "No vectors created"
        
        # Check for errors (warnings are OK)
        errors = [e for e in result.get("error_log", []) if "error" in e]
        assert len(errors) == 0, f"Pipeline had errors: {errors}"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_markdown_file_ingestion(
        self,
        test_channel_id: str,
        simple_embedder,
        tmp_path,
    ):
        """Test ingestion of a markdown file."""
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        # Create markdown file
        md_content = """# Test Document

## Section 1

This is the first section with some content.

## Section 2

This is the second section with more content.

- Item 1
- Item 2
- Item 3
"""
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)
        
        result = await run_simplified_pipeline(
            file_path=md_file,
            channel_id=test_channel_id,
            simple_embedder=simple_embedder,
        )
        
        assert result["processing_stage"] in ("finalize", "completed")
        assert len(result["chunks"]) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_channel_isolation(
        self,
        simple_embedder,
        tmp_path,
    ):
        """Test that different channels are isolated."""
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        channel_a = f"test_ch_a_{uuid.uuid4().hex[:8]}"
        channel_b = f"test_ch_b_{uuid.uuid4().hex[:8]}"
        
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for channel isolation test.")
        
        # Ingest to channel A
        result_a = await run_simplified_pipeline(
            file_path=test_file,
            channel_id=channel_a,
            simple_embedder=simple_embedder,
        )
        
        assert result_a["processing_stage"] in ("finalize", "completed")
        
        # Verify channel A has data
        from core.storage.vector_store import get_vector_client
        from core.storage.channel_utils import channel_collection_name
        
        vector_client = get_vector_client()
        collection_a = channel_collection_name(channel_a, "test_kb", 1)
        
        # Channel B should not have this collection
        collection_b = channel_collection_name(channel_b, "test_kb", 1)
        
        exists_a = await vector_client.collection_exists(collection_a)
        exists_b = await vector_client.collection_exists(collection_b)
        
        assert exists_a, "Channel A collection should exist"
        assert not exists_b, "Channel B collection should not exist"


# =============================================================================
# ZIP Bomb Protection Tests (No external services needed)
# =============================================================================

class TestZipBombProtection:
    """Test ZIP bomb protection without external services."""
    
    @pytest.mark.asyncio
    async def test_zip_with_too_many_files_rejected(self, tmp_path):
        """Test that ZIP with >100 files is rejected."""
        import zipfile
        from core.ingestion.nodes.loader import LoaderNode
        from unittest.mock import AsyncMock, patch
        
        # Create ZIP with 101 files
        zip_path = tmp_path / "bomb.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in range(101):
                zf.writestr(f"file_{i}.txt", f"content {i}")
        
        # Mock blob store to return our ZIP
        mock_store = AsyncMock()
        mock_store.exists = AsyncMock(return_value=True)
        mock_store.head = AsyncMock(return_value={"size": zip_path.stat().st_size})
        mock_store.get = AsyncMock(return_value=zip_path.read_bytes())
        
        state = {
            "file_path": str(zip_path),
            "file_type": "zip",
            "error_log": [],
            "progress": {},
        }
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_store):
            loader = LoaderNode()
            result = await loader(state)
        
        # Should have zip bomb error
        error_messages = str(result.get("error_log", []))
        assert "zip_bomb_protection" in error_messages, \
            f"Expected zip_bomb_protection error, got: {result['error_log']}"
    
    @pytest.mark.asyncio
    async def test_normal_zip_accepted(self, tmp_path):
        """Test that normal ZIP files are accepted."""
        import zipfile
        from core.ingestion.nodes.loader import LoaderNode
        from unittest.mock import AsyncMock, patch
        
        # Create ZIP with 10 files (under limit)
        zip_path = tmp_path / "normal.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in range(10):
                zf.writestr(f"file_{i}.txt", f"content {i}")
        
        mock_store = AsyncMock()
        mock_store.exists = AsyncMock(return_value=True)
        mock_store.head = AsyncMock(return_value={"size": zip_path.stat().st_size})
        mock_store.get = AsyncMock(return_value=zip_path.read_bytes())
        
        state = {
            "file_path": str(zip_path),
            "file_type": "zip",
            "error_log": [],
            "progress": {},
        }
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_store):
            loader = LoaderNode()
            result = await loader(state)
        
        # Should NOT have zip bomb error
        error_messages = str(result.get("error_log", []))
        assert "zip_bomb_protection" not in error_messages


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
