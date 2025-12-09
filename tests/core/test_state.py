"""Tests for core.state module."""

import pytest

from core.state import (
    AlgorithmConfig,
    ChunkingStrategy,
    ChunkMetadata,
    IngestState,
    RetrievalState,
    StrategyConfig,
)


class TestStrategyConfig:
    """Tests for StrategyConfig Pydantic model."""

    @pytest.mark.unit
    def test_default_values(self):
        """Test default values are correctly set."""
        config = StrategyConfig()
        assert config.ocr_provider == "auto"
        assert config.embedding_model == "BAAI/bge-m3"
        assert config.vector_backend == "auto"
        assert config.enable_quantization is True

    @pytest.mark.unit
    def test_custom_values(self):
        """Test custom values override defaults."""
        config = StrategyConfig(
            ocr_provider="qwen-vl",
            embedding_model="text-embedding-3-small",
            vector_backend="qdrant",
        )
        assert config.ocr_provider == "qwen-vl"
        assert config.embedding_model == "text-embedding-3-small"
        assert config.vector_backend == "qdrant"

    @pytest.mark.unit
    def test_nested_chunking(self):
        """Test nested ChunkingStrategy."""
        config = StrategyConfig(chunking=ChunkingStrategy(mode="semantic", chunk_size=1024))
        assert config.chunking.mode == "semantic"
        assert config.chunking.chunk_size == 1024

    @pytest.mark.unit
    def test_algorithm_config(self):
        """Test AlgorithmConfig nested object."""
        config = StrategyConfig(
            algorithms=AlgorithmConfig(enable_raptor=True, raptor_max_cluster=20)
        )
        assert config.algorithms.enable_raptor is True
        assert config.algorithms.raptor_max_cluster == 20


class TestStateAnnotations:
    """Tests for TypedDict state definitions."""

    @pytest.mark.unit
    def test_chunk_metadata_has_channel_id(self):
        """Test ChunkMetadata includes channel_id."""
        assert "channel_id" in ChunkMetadata.__annotations__

    @pytest.mark.unit
    def test_ingest_state_has_channel_id(self):
        """Test IngestState includes channel_id."""
        assert "channel_id" in IngestState.__annotations__

    @pytest.mark.unit
    def test_retrieval_state_has_channel_id(self):
        """Test RetrievalState includes channel_id."""
        assert "channel_id" in RetrievalState.__annotations__

    @pytest.mark.unit
    def test_retrieval_state_has_session_id(self):
        """Test RetrievalState includes session_id."""
        assert "session_id" in RetrievalState.__annotations__

    @pytest.mark.unit
    def test_retrieval_state_has_kb_names(self):
        """Test RetrievalState includes kb_names (list)."""
        assert "kb_names" in RetrievalState.__annotations__
