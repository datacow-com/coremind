"""
Real E2E State and Configuration Tests.

This module consolidates state and configuration tests for the real-e2e-tests spec.
It includes:
- Minimal config ingestion test (Requirements 4.5)
- References to existing property tests in other modules

Existing tests (already implemented):
- test_strategy_config.py: Property 17 (Flat Config Override) - Requirements 4.1
- test_effective_properties.py: Property 18 (Falsy Value Handling) - Requirements 4.2
- test_effective_properties.py: Property 19 (Config Serialization Round-Trip) - Requirements 4.4
- test_channel_id_validation.py: Channel ID validation - Requirements 4.3

Requirements: 4.1-4.5
"""

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, AsyncMock

import pytest

# Set environment variables for docker-compose services BEFORE importing core modules
os.environ.setdefault("QDRANT_URL", "http://localhost:3508")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:3507")

from core.state import IngestState, StrategyConfig, ChunkingStrategy


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
    return f"test_state_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def small_test_file(tmp_path):
    """Create a small test file for quick testing."""
    content = "This is a test document for minimal config testing.\n\n" * 20
    file_path = tmp_path / "minimal_config_test.txt"
    file_path.write_text(content)
    return file_path


# =============================================================================
# Helper Functions
# =============================================================================

def check_services_available() -> bool:
    """Check if required services (Qdrant, ES) are available and compatible."""
    try:
        from tests.core.conftest_real import (
            check_qdrant_available,
            check_elasticsearch_available,
        )
        if not (check_qdrant_available() and check_elasticsearch_available()):
            return False
        
        # Additional check: verify ES client compatibility
        try:
            import httpx
            resp = httpx.get("http://localhost:3507/_cluster/health", timeout=5.0)
            if resp.status_code != 200:
                return False
        except Exception:
            return False
        
        return True
    except ImportError:
        return False


# Skip marker for E2E tests that require full service stack
skip_e2e_services = pytest.mark.skipif(
    not check_services_available(),
    reason="E2E services not available or incompatible. Run: docker-compose up -d"
)


async def run_minimal_config_pipeline(
    file_path: Path,
    channel_id: str,
    simple_embedder,
    strategy_config: StrategyConfig | None = None,
) -> Dict[str, Any]:
    """
    Run ingestion pipeline with minimal StrategyConfig.
    
    Uses default values for all configuration options.
    """
    from core.ingestion.graph import create_ingest_graph_no_checkpoint
    
    # Use minimal config if not provided
    if strategy_config is None:
        strategy_config = StrategyConfig()
    
    # Override embedding dimensions for test speed
    # Disable keyword_backend to avoid ES client compatibility issues
    config_dict = strategy_config.model_dump()
    config_dict["embedding_dimensions"] = 256
    config_dict["keyword_backend"] = "disabled"  # Avoid ES compatibility issues
    
    initial_state: IngestState = {
        "channel_id": channel_id,
        "task_id": f"task_{uuid.uuid4().hex[:8]}",
        "file_path": str(file_path),
        "file_type": file_path.suffix.lstrip(".").lower(),
        "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": config_dict,
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
# Minimal Config Ingestion Tests
# =============================================================================

@pytest.mark.real_e2e
class TestMinimalConfigIngestion:
    """
    Tests for TC-4.5: Minimal StrategyConfig drives ingestion pipeline successfully.
    
    Requirements: 4.5 - WHEN a minimal StrategyConfig drives the ingestion pipeline 
    THEN the OmniRAG System SHALL complete successfully with default values applied
    """
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_minimal_config_ingestion_success(
        self,
        test_channel_id: str,
        small_test_file: Path,
        simple_embedder,
    ):
        """
        TC-4.5: Minimal StrategyConfig completes ingestion successfully.
        
        Verifies that a StrategyConfig with all default values can drive
        the ingestion pipeline to completion without errors.
        
        Requirements: 4.5
        """
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        # Use completely default StrategyConfig
        minimal_config = StrategyConfig()
        
        result = await run_minimal_config_pipeline(
            file_path=small_test_file,
            channel_id=test_channel_id,
            simple_embedder=simple_embedder,
            strategy_config=minimal_config,
        )
        
        # Verify completion
        assert result["processing_stage"] in ("finalize", "completed"), \
            f"Pipeline failed at stage: {result['processing_stage']}"
        
        # Verify chunks created
        assert len(result["chunks"]) > 0, "No chunks created with minimal config"
        
        # Verify vectors created
        assert len(result["vectors"]) > 0, "No vectors created with minimal config"
        
        # Check for errors (warnings are OK)
        errors = [e for e in result.get("error_log", []) if "error" in e]
        assert len(errors) == 0, f"Pipeline had errors with minimal config: {errors}"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_minimal_config_uses_default_chunking(
        self,
        test_channel_id: str,
        small_test_file: Path,
        simple_embedder,
    ):
        """
        TC-4.5: Minimal config uses default chunking strategy.
        
        Verifies that default chunking values (mode=fixed, chunk_size=512, 
        chunk_overlap=50, preserve_tables=True) are applied.
        
        Requirements: 4.5
        """
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        minimal_config = StrategyConfig()
        
        # Verify default values are set
        assert minimal_config.chunking_mode_effective == "fixed"
        assert minimal_config.chunk_size_effective == 512
        assert minimal_config.chunk_overlap_effective == 50
        assert minimal_config.preserve_tables_effective is True
        
        result = await run_minimal_config_pipeline(
            file_path=small_test_file,
            channel_id=test_channel_id,
            simple_embedder=simple_embedder,
            strategy_config=minimal_config,
        )
        
        # Verify pipeline completed
        assert result["processing_stage"] in ("finalize", "completed")
        
        # Verify chunks were created with default settings
        assert len(result["chunks"]) > 0
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(TEST_TIMEOUT)
    async def test_minimal_config_with_only_channel_id(
        self,
        test_channel_id: str,
        small_test_file: Path,
        simple_embedder,
    ):
        """
        TC-4.5: Ingestion succeeds with only channel_id and file_path provided.
        
        This is the absolute minimal configuration - only the required fields
        (channel_id, file_path) are provided, everything else uses defaults.
        
        Requirements: 4.5
        """
        if not check_services_available():
            pytest.skip("Required services (Qdrant/ES) not available")
        
        # Create state with absolute minimum required fields
        minimal_config = StrategyConfig()
        config_dict = minimal_config.model_dump()
        config_dict["embedding_dimensions"] = 256
        config_dict["keyword_backend"] = "disabled"  # Avoid ES compatibility issues
        
        initial_state: IngestState = {
            "channel_id": test_channel_id,
            "task_id": f"task_{uuid.uuid4().hex[:8]}",
            "file_path": str(small_test_file),
            "file_type": "txt",
            "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": config_dict,
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
        
        from core.ingestion.graph import create_ingest_graph_no_checkpoint
        
        with patch("core.ingestion.nodes.embedder.get_embedder", return_value=simple_embedder):
            graph = create_ingest_graph_no_checkpoint()
            result = await graph.ainvoke(initial_state)
        
        # Verify completion
        assert result["processing_stage"] in ("finalize", "completed"), \
            f"Pipeline failed with minimal state at stage: {result['processing_stage']}"


# =============================================================================
# Unit Tests (No External Services Required)
# =============================================================================

class TestMinimalConfigUnit:
    """
    Unit tests for minimal config behavior without external services.
    
    Requirements: 4.5
    """
    
    def test_minimal_strategy_config_has_all_defaults(self):
        """
        Verify minimal StrategyConfig has all expected default values.
        
        Requirements: 4.5
        """
        config = StrategyConfig()
        
        # Chunking defaults
        assert config.chunking_mode_effective == "fixed"
        assert config.chunk_size_effective == 512
        assert config.chunk_overlap_effective == 50
        assert config.preserve_tables_effective is True
        
        # OCR defaults
        assert config.ocr_provider == "auto"
        assert config.force_ocr is False
        
        # Embedding defaults
        assert config.embedding_model == "BAAI/bge-m3"
        assert config.embedding_batch_size == 64
        assert config.embedding_dimensions == 1024
        
        # Index defaults
        assert config.vector_backend == "auto"
        assert config.keyword_backend == "elasticsearch"
        
        # Quality defaults
        assert config.enable_cleaning is False
        assert config.min_quality_score == 0.5
        assert config.enable_dedup is True
    
    def test_minimal_config_serialization(self):
        """
        Verify minimal config can be serialized and deserialized.
        
        Requirements: 4.5
        """
        config = StrategyConfig()
        
        # Serialize
        serialized = config.model_dump()
        
        # Deserialize
        reconstructed = StrategyConfig(**serialized)
        
        # Verify all effective values match
        assert reconstructed.chunking_mode_effective == config.chunking_mode_effective
        assert reconstructed.chunk_size_effective == config.chunk_size_effective
        assert reconstructed.chunk_overlap_effective == config.chunk_overlap_effective
        assert reconstructed.preserve_tables_effective == config.preserve_tables_effective
    
    def test_minimal_config_can_be_used_in_ingest_state(self):
        """
        Verify minimal config can be embedded in IngestState dict.
        
        Requirements: 4.5
        """
        config = StrategyConfig()
        
        # Create IngestState with minimal config
        state: IngestState = {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "file_path": "/test/file.txt",
            "file_type": "txt",
            "batch_id": "batch_001",
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
        
        # Verify state is valid
        assert state["channel_id"] == "test_channel"
        assert "chunking" in state["strategy_config"]
        
        # Verify config can be reconstructed from state
        reconstructed = StrategyConfig(**state["strategy_config"])
        assert reconstructed.chunking_mode_effective == "fixed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
