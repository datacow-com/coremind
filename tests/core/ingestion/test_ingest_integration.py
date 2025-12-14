"""
Integration tests for ingestion pipeline.

These tests use MOCKED external services to verify pipeline logic
without depending on real infrastructure.

This is the correct approach for CI/CD and reliable testing.
"""

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test constants
TEST_DOCS_DIR = Path(__file__).parent.parent / "docs"


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_blob_store():
    """Mock blob store that returns test file content."""
    store = AsyncMock()
    store.exists = AsyncMock(return_value=True)
    store.head = AsyncMock(return_value={"size": 1024})  # Small file
    store.get = AsyncMock(return_value=b"Test content for parsing")
    return store


@pytest.fixture
def mock_vector_client():
    """Mock Qdrant client."""
    client = AsyncMock()
    client.ensure_collection = AsyncMock()
    client.upsert = AsyncMock()
    return client


@pytest.fixture
def mock_keyword_client():
    """Mock Elasticsearch client."""
    client = AsyncMock()
    client.ensure_index = AsyncMock()
    client.bulk_upsert = AsyncMock()
    return client


@pytest.fixture
def mock_embedder():
    """Mock embedder that returns fake vectors."""
    import numpy as np
    
    embedder = MagicMock()
    
    def fake_embed_batch(texts):
        # Return random vectors of correct dimension
        return np.random.rand(len(texts), 1024).astype(np.float32)
    
    embedder.embed_batch = fake_embed_batch
    embedder._ensure_config = AsyncMock()
    return embedder


@pytest.fixture
def base_ingest_state():
    """Base state for ingestion tests."""
    return {
        "channel_id": f"test_ch_{uuid.uuid4().hex[:8]}",
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "file_path": "test.pdf",
        "file_type": "pdf",
        "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": {
            "chunking_mode": "fixed",
            "chunk_size": 500,
            "chunk_overlap": 50,
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


# =============================================================================
# Unit Tests for Individual Nodes
# =============================================================================

class TestLoaderNode:
    """Test loader node in isolation."""
    
    @pytest.mark.asyncio
    async def test_loader_small_file(self, base_ingest_state, mock_blob_store):
        """Test loading a small file into memory."""
        from core.ingestion.nodes.loader import LoaderNode
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_blob_store):
            loader = LoaderNode()
            result = await loader(base_ingest_state)
        
        assert result["raw_content"] == b"Test content for parsing"
        assert result["lazy_load"] is False
        assert result["processing_stage"] == "parse"
    
    @pytest.mark.asyncio
    async def test_loader_large_file_triggers_lazy_load(self, base_ingest_state, mock_blob_store):
        """Test that large files trigger lazy loading."""
        from core.ingestion.nodes.loader import LoaderNode, LARGE_FILE_THRESHOLD
        
        # Make file larger than threshold
        mock_blob_store.head = AsyncMock(return_value={"size": LARGE_FILE_THRESHOLD + 1024})
        mock_blob_store.download_to_file = AsyncMock()
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_blob_store):
            loader = LoaderNode()
            result = await loader(base_ingest_state)
        
        assert result["lazy_load"] is True
        assert result["raw_content"] is None


class TestZipBombProtection:
    """Test ZIP bomb protection."""
    
    @pytest.mark.asyncio
    async def test_zip_bomb_file_count_protection(self, base_ingest_state, mock_blob_store):
        """Test that ZIP with >100 files is rejected."""
        import zipfile
        import io
        
        # Create a ZIP with 101 files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for i in range(101):
                zf.writestr(f"file_{i}.txt", f"content {i}")
        
        mock_blob_store.get = AsyncMock(return_value=zip_buffer.getvalue())
        base_ingest_state["file_type"] = "zip"
        
        from core.ingestion.nodes.loader import LoaderNode
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_blob_store):
            loader = LoaderNode()
            result = await loader(base_ingest_state)
        
        # Should have error about zip bomb
        error_messages = [str(e) for e in result.get("error_log", [])]
        assert any("zip_bomb_protection" in msg for msg in error_messages), \
            f"Expected zip_bomb_protection error, got: {error_messages}"


class TestCpuParser:
    """Test CPU parser in isolation."""
    
    @pytest.mark.asyncio
    async def test_parse_text_content(self, base_ingest_state):
        """Test parsing plain text."""
        from core.ingestion.nodes.parser.cpu_parser import CpuTextParser
        
        base_ingest_state["raw_content"] = b"Hello world\n\nThis is a test."
        base_ingest_state["file_type"] = "txt"
        
        parser = CpuTextParser()
        result = await parser(base_ingest_state)
        
        assert len(result["parsed_blocks"]) > 0
        assert result["parsed_blocks"][0]["type"] == "text"
    
    @pytest.mark.asyncio
    async def test_parse_markdown(self, base_ingest_state):
        """Test parsing markdown."""
        from core.ingestion.nodes.parser.cpu_parser import CpuTextParser
        
        base_ingest_state["raw_content"] = b"# Title\n\nParagraph 1\n\nParagraph 2"
        base_ingest_state["file_type"] = "md"
        
        parser = CpuTextParser()
        result = await parser(base_ingest_state)
        
        assert len(result["parsed_blocks"]) > 0


class TestChunker:
    """Test chunker in isolation."""
    
    @pytest.mark.asyncio
    async def test_chunker_creates_chunks(self, base_ingest_state):
        """Test that chunker creates chunks from parsed blocks."""
        from core.ingestion.nodes.chunker import SmartChunker
        
        base_ingest_state["parsed_blocks"] = [
            {"type": "text", "content": "A" * 1000, "page": 1},
            {"type": "text", "content": "B" * 1000, "page": 2},
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_ingest_state)
        
        assert len(result["chunks"]) > 0
        for chunk in result["chunks"]:
            assert "id" in chunk
            assert "content" in chunk
            assert "doc_id" in chunk


class TestEmbedder:
    """Test embedder with mocked model."""
    
    @pytest.mark.asyncio
    async def test_embedder_creates_vectors(self, base_ingest_state, mock_embedder):
        """Test that embedder creates vectors for chunks."""
        from core.ingestion.nodes.embedder import BatchEmbedder
        
        base_ingest_state["chunks"] = [
            {"id": "chunk_1", "content": "Test content 1", "doc_id": "doc1", "chunk_index": 0, "metadata": {}},
            {"id": "chunk_2", "content": "Test content 2", "doc_id": "doc1", "chunk_index": 1, "metadata": {}},
        ]
        
        with patch("core.ingestion.nodes.embedder.get_embedder", return_value=mock_embedder):
            embedder = BatchEmbedder()
            result = await embedder(base_ingest_state)
        
        assert len(result["vectors"]) == 2
        assert len(result["vectors"][0]) == 1024  # Embedding dimension


class TestIndexer:
    """Test indexer with mocked backends."""
    
    @pytest.mark.asyncio
    async def test_indexer_writes_to_both_backends(
        self, base_ingest_state, mock_vector_client, mock_keyword_client
    ):
        """Test that indexer writes to both Qdrant and ES."""
        from core.ingestion.nodes.indexer import DualIndexer
        import numpy as np
        
        base_ingest_state["chunks"] = [
            {"id": "chunk_1", "content": "Test", "doc_id": "doc1", "chunk_index": 0, "metadata": {}},
        ]
        base_ingest_state["vectors"] = [np.random.rand(1024).tolist()]
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client):
            with patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
                indexer = DualIndexer()
                result = await indexer(base_ingest_state)
        
        mock_vector_client.ensure_collection.assert_called()
        mock_vector_client.upsert.assert_called()
        mock_keyword_client.ensure_index.assert_called()
        mock_keyword_client.bulk_upsert.assert_called()


# =============================================================================
# Integration Test: Full Pipeline with Mocks
# =============================================================================

class TestFullPipelineWithMocks:
    """Test full pipeline with all external services mocked."""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_text_file(
        self, 
        base_ingest_state, 
        mock_blob_store, 
        mock_vector_client, 
        mock_keyword_client,
        mock_embedder,
    ):
        """Test full pipeline with a simple text file."""
        from core.ingestion.graph import create_ingest_graph_no_checkpoint
        
        # Setup mocks
        mock_blob_store.get = AsyncMock(return_value=b"Hello world. " * 100)
        base_ingest_state["file_type"] = "txt"
        
        with patch("core.ingestion.nodes.loader.get_blob_store", return_value=mock_blob_store):
            with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client):
                with patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
                    with patch("core.ingestion.nodes.embedder.get_embedder", return_value=mock_embedder):
                        graph = create_ingest_graph_no_checkpoint()
                        result = await graph.ainvoke(base_ingest_state)
        
        # Verify pipeline completed
        assert result["processing_stage"] in ("finalize", "completed")
        assert len(result["chunks"]) > 0
        assert len(result["vectors"]) > 0
        assert len(result["error_log"]) == 0 or all(
            "warning" in e for e in result["error_log"]
        )


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestPropertyBased:
    """Property-based tests using Hypothesis."""
    
    def test_channel_naming_convention(self):
        """Test channel naming follows convention."""
        from core.storage.channel_utils import channel_collection_name, channel_index_name
        
        channel_id = "test_channel_123"
        kb_name = "my_kb"
        version = 1
        
        collection = channel_collection_name(channel_id, kb_name, version)
        index = channel_index_name(channel_id, kb_name)
        
        assert collection.startswith(f"ch_{channel_id}_")
        assert index.startswith(f"ch_{channel_id}_")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
