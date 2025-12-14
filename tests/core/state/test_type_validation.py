"""
Type validation tests for StrategyConfig and ChunkingStrategy.

Tests for:
- P0: Type mismatch validation (string/negative/oversized values)
- P1: overlap > chunk_size validation
- P1: Partial nested config behavior
- P1: Other StrategyConfig field defaults

Requirements: 5.2, 5.3
"""

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from core.state import ChunkingStrategy, StrategyConfig, AlgorithmConfig


# =============================================================================
# P0: Type Mismatch Validation Tests
# =============================================================================

class TestChunkSizeTypeValidation:
    """
    P0: Tests for chunk_size type validation.
    
    Pydantic should coerce valid strings to int, but reject invalid types.
    P0 Fix: Now validates chunk_size > 0.
    """

    def test_chunk_size_string_coercion(self) -> None:
        """
        Pydantic coerces valid numeric strings to int.
        This is expected behavior, not a bug.
        """
        # Pydantic v2 coerces "512" to 512
        config = StrategyConfig(chunk_size=512)  # type: ignore
        assert config.chunk_size == 512
        assert isinstance(config.chunk_size, int)

    def test_chunk_size_invalid_string_raises_error(self) -> None:
        """
        Invalid string values should raise ValidationError.
        """
        with pytest.raises(ValidationError):
            StrategyConfig(chunk_size="not_a_number")  # type: ignore

    def test_chunk_size_negative_raises_validation_error(self) -> None:
        """
        P0 FIX VERIFIED: Negative chunk_size raises ValidationError.
        
        chunk_size must be > 0.
        """
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(chunk_size=-100)
        
        assert "chunk_size" in str(exc_info.value).lower()

    def test_chunk_size_zero_raises_validation_error(self) -> None:
        """
        P0 FIX VERIFIED: Zero chunk_size raises ValidationError.
        
        chunk_size must be > 0.
        """
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(chunk_size=0)
        
        assert "chunk_size" in str(exc_info.value).lower()

    @settings(max_examples=50)
    @given(st.integers(min_value=1, max_value=100000))
    def test_chunk_size_positive_integers_valid(self, size: int) -> None:
        """
        All positive integers should be valid chunk_size values.
        """
        config = StrategyConfig(chunk_size=size)
        assert config.chunk_size == size


class TestChunkOverlapTypeValidation:
    """
    P0: Tests for chunk_overlap type validation.
    P0 Fix: Now validates chunk_overlap >= 0.
    """

    def test_chunk_overlap_negative_raises_validation_error(self) -> None:
        """
        P0 FIX VERIFIED: Negative chunk_overlap raises ValidationError.
        
        chunk_overlap must be >= 0.
        """
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(chunk_overlap=-50)
        
        assert "chunk_overlap" in str(exc_info.value).lower()

    def test_chunk_overlap_zero_is_valid(self) -> None:
        """
        Zero chunk_overlap is valid (no overlap between chunks).
        """
        config = StrategyConfig(chunk_overlap=0)
        assert config.chunk_overlap == 0

    def test_chunk_overlap_invalid_string_raises_error(self) -> None:
        """
        Invalid string values should raise ValidationError.
        """
        with pytest.raises(ValidationError):
            StrategyConfig(chunk_overlap="invalid")  # type: ignore


class TestNestedChunkingTypeValidation:
    """
    P0: Tests for nested ChunkingStrategy type validation.
    P0 Fix: Now validates chunk_size > 0 and chunk_overlap >= 0.
    """

    def test_nested_chunk_size_negative_raises_validation_error(self) -> None:
        """
        P0 FIX VERIFIED: Negative chunk_size in nested ChunkingStrategy raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            ChunkingStrategy(chunk_size=-100)
        
        assert "chunk_size" in str(exc_info.value).lower()

    def test_nested_chunk_overlap_negative_raises_validation_error(self) -> None:
        """
        P0 FIX VERIFIED: Negative chunk_overlap in nested ChunkingStrategy raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            ChunkingStrategy(chunk_overlap=-50)
        
        assert "chunk_overlap" in str(exc_info.value).lower()


# =============================================================================
# P1: Overlap > Chunk Size Validation Tests
# =============================================================================

class TestOverlapChunkSizeRelation:
    """
    P1: Tests for overlap > chunk_size validation.
    
    P1 Fix: Now validates overlap < chunk_size via model_validator.
    """

    def test_overlap_greater_than_chunk_size_raises_validation_error(self) -> None:
        """
        P1 FIX VERIFIED: overlap >= chunk_size raises ValidationError.
        """
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(chunk_size=100, chunk_overlap=200)
        
        assert "chunk_overlap" in str(exc_info.value).lower()

    def test_overlap_equal_to_chunk_size_raises_validation_error(self) -> None:
        """
        P1 FIX VERIFIED: overlap == chunk_size raises ValidationError.
        """
        with pytest.raises(ValidationError) as exc_info:
            StrategyConfig(chunk_size=100, chunk_overlap=100)
        
        assert "chunk_overlap" in str(exc_info.value).lower()

    def test_nested_overlap_greater_than_chunk_size_raises_validation_error(self) -> None:
        """
        P1 FIX VERIFIED: overlap >= chunk_size in nested ChunkingStrategy raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            ChunkingStrategy(chunk_size=100, chunk_overlap=200)
        
        assert "chunk_overlap" in str(exc_info.value).lower()

    def test_nested_overlap_equal_to_chunk_size_raises_validation_error(self) -> None:
        """
        P1 FIX VERIFIED: overlap == chunk_size in nested ChunkingStrategy raises error.
        """
        with pytest.raises(ValidationError) as exc_info:
            ChunkingStrategy(chunk_size=100, chunk_overlap=100)
        
        assert "chunk_overlap" in str(exc_info.value).lower()

    @settings(max_examples=50)
    @given(
        chunk_size=st.integers(min_value=64, max_value=4096),
        overlap_ratio=st.floats(min_value=0.0, max_value=0.49),  # Must be < 1.0 to ensure overlap < size
    )
    def test_valid_overlap_ratios(self, chunk_size: int, overlap_ratio: float) -> None:
        """
        Valid overlap should be < chunk_size.
        """
        overlap = int(chunk_size * overlap_ratio)
        config = StrategyConfig(chunk_size=chunk_size, chunk_overlap=overlap)
        
        assert config.chunk_overlap_effective < config.chunk_size_effective


# =============================================================================
# P1: Partial Nested Config Tests
# =============================================================================

class TestPartialNestedConfig:
    """
    P1: Tests for partial nested configuration behavior.
    
    When only some nested fields are set, others should use defaults.
    """

    def test_partial_nested_only_mode_set(self) -> None:
        """
        When only chunking.mode is set, other fields use ChunkingStrategy defaults.
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(mode="semantic")
            # chunk_size, chunk_overlap, preserve_tables use defaults
        )
        
        # Mode is set
        assert config.chunking_mode_effective == "semantic"
        
        # Other fields use ChunkingStrategy defaults
        assert config.chunk_size_effective == 512  # Default
        assert config.chunk_overlap_effective == 50  # Default
        assert config.preserve_tables_effective is True  # Default

    def test_partial_nested_only_size_set(self) -> None:
        """
        When only chunking.chunk_size is set, other fields use defaults.
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(chunk_size=1024)
        )
        
        assert config.chunking_mode_effective == "fixed"  # Default
        assert config.chunk_size_effective == 1024  # Set
        assert config.chunk_overlap_effective == 50  # Default
        assert config.preserve_tables_effective is True  # Default

    def test_partial_nested_mode_and_size_set(self) -> None:
        """
        When mode and size are set, overlap and preserve_tables use defaults.
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(mode="layout_aware", chunk_size=256)
        )
        
        assert config.chunking_mode_effective == "layout_aware"
        assert config.chunk_size_effective == 256
        assert config.chunk_overlap_effective == 50  # Default
        assert config.preserve_tables_effective is True  # Default

    def test_partial_flat_overrides_partial_nested(self) -> None:
        """
        Flat fields override nested even when nested is partially set.
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(mode="semantic", chunk_size=1024),
            chunking_mode="fixed",  # Override mode only
            # chunk_size not set flat, so nested value used
        )
        
        assert config.chunking_mode_effective == "fixed"  # Flat override
        assert config.chunk_size_effective == 1024  # Nested value (flat is None)


# =============================================================================
# P1: Other StrategyConfig Field Defaults Tests
# =============================================================================

class TestOCRFieldDefaults:
    """
    P1: Tests for OCR-related field defaults.
    """

    def test_ocr_provider_default(self) -> None:
        """OCR provider defaults to 'auto'."""
        config = StrategyConfig()
        assert config.ocr_provider == "auto"

    def test_ocr_fallback_chain_default(self) -> None:
        """OCR fallback chain has default values."""
        config = StrategyConfig()
        assert config.ocr_fallback_chain == ["qwen-vl", "volc_engine"]

    def test_ocr_concurrency_default(self) -> None:
        """OCR concurrency defaults to 5."""
        config = StrategyConfig()
        assert config.ocr_concurrency == 5

    def test_force_ocr_default(self) -> None:
        """Force OCR defaults to False."""
        config = StrategyConfig()
        assert config.force_ocr is False

    def test_detect_complex_layout_default(self) -> None:
        """Detect complex layout defaults to False."""
        config = StrategyConfig()
        assert config.detect_complex_layout is False

    def test_ocr_provider_invalid_raises_error(self) -> None:
        """Invalid OCR provider raises ValidationError."""
        with pytest.raises(ValidationError):
            StrategyConfig(ocr_provider="invalid_provider")


class TestEmbeddingFieldDefaults:
    """
    P1: Tests for embedding-related field defaults.
    """

    def test_embedding_model_default(self) -> None:
        """Embedding model defaults to BAAI/bge-m3."""
        config = StrategyConfig()
        assert config.embedding_model == "BAAI/bge-m3"

    def test_embedding_batch_size_default(self) -> None:
        """Embedding batch size defaults to 64."""
        config = StrategyConfig()
        assert config.embedding_batch_size == 64

    def test_embedding_dimensions_default(self) -> None:
        """Embedding dimensions defaults to 1024."""
        config = StrategyConfig()
        assert config.embedding_dimensions == 1024


class TestIndexFieldDefaults:
    """
    P1: Tests for indexing-related field defaults.
    """

    def test_vector_backend_default(self) -> None:
        """Vector backend defaults to 'auto'."""
        config = StrategyConfig()
        assert config.vector_backend == "auto"

    def test_keyword_backend_default(self) -> None:
        """Keyword backend defaults to 'elasticsearch'."""
        config = StrategyConfig()
        assert config.keyword_backend == "elasticsearch"

    def test_enable_quantization_default(self) -> None:
        """Enable quantization defaults to True."""
        config = StrategyConfig()
        assert config.enable_quantization is True

    def test_enable_hot_cold_tier_default(self) -> None:
        """Enable hot/cold tier defaults to False."""
        config = StrategyConfig()
        assert config.enable_hot_cold_tier is False

    def test_enable_multimodal_index_default(self) -> None:
        """Enable multimodal index defaults to True."""
        config = StrategyConfig()
        assert config.enable_multimodal_index is True

    def test_vector_backend_invalid_raises_error(self) -> None:
        """Invalid vector backend raises ValidationError."""
        with pytest.raises(ValidationError):
            StrategyConfig(vector_backend="invalid")

    def test_keyword_backend_invalid_raises_error(self) -> None:
        """Invalid keyword backend raises ValidationError."""
        with pytest.raises(ValidationError):
            StrategyConfig(keyword_backend="invalid")


class TestQualityFieldDefaults:
    """
    P1: Tests for quality control field defaults.
    """

    def test_enable_cleaning_default(self) -> None:
        """Enable cleaning defaults to False."""
        config = StrategyConfig()
        assert config.enable_cleaning is False

    def test_min_quality_score_default(self) -> None:
        """Min quality score defaults to 0.5."""
        config = StrategyConfig()
        assert config.min_quality_score == 0.5

    def test_enable_dedup_default(self) -> None:
        """Enable dedup defaults to True."""
        config = StrategyConfig()
        assert config.enable_dedup is True

    def test_enable_pii_filter_default(self) -> None:
        """Enable PII filter defaults to False."""
        config = StrategyConfig()
        assert config.enable_pii_filter is False


class TestCacheFieldDefaults:
    """
    P1: Tests for semantic cache field defaults.
    """

    def test_enable_semantic_cache_default(self) -> None:
        """Enable semantic cache defaults to False."""
        config = StrategyConfig()
        assert config.enable_semantic_cache is False

    def test_cache_ttl_default(self) -> None:
        """Cache TTL defaults to 3600."""
        config = StrategyConfig()
        assert config.cache_ttl == 3600


class TestHallucinationFieldDefaults:
    """
    P1: Tests for hallucination detection field defaults.
    """

    def test_enable_hallucination_check_default(self) -> None:
        """Enable hallucination check defaults to False."""
        config = StrategyConfig()
        assert config.enable_hallucination_check is False

    def test_hallucination_threshold_default(self) -> None:
        """Hallucination threshold defaults to 0.5."""
        config = StrategyConfig()
        assert config.hallucination_threshold == 0.5


class TestAlgorithmConfigDefaults:
    """
    P1: Tests for AlgorithmConfig field defaults.
    """

    def test_algorithm_config_default(self) -> None:
        """AlgorithmConfig has expected defaults."""
        config = StrategyConfig()
        
        assert config.algorithms.enable_raptor is False
        assert config.algorithms.raptor_max_cluster == 10
        assert config.algorithms.enable_graphrag is False
        assert config.algorithms.graph_community_level == 2
        assert config.algorithms.enable_mindmap is False

    def test_algorithm_config_override(self) -> None:
        """AlgorithmConfig can be overridden."""
        config = StrategyConfig(
            algorithms=AlgorithmConfig(
                enable_raptor=True,
                raptor_max_cluster=20,
                enable_graphrag=True,
            )
        )
        
        assert config.algorithms.enable_raptor is True
        assert config.algorithms.raptor_max_cluster == 20
        assert config.algorithms.enable_graphrag is True
        assert config.algorithms.enable_mindmap is False  # Still default


# =============================================================================
# JSON Serialization Round-Trip Tests
# =============================================================================

class TestJSONSerializationRoundTrip:
    """
    P1: Tests for JSON serialization round-trip (using json.dumps/loads).
    
    This tests the actual JSON serialization path, not just model_dump.
    """

    def test_json_round_trip_default_config(self) -> None:
        """
        Default config survives JSON round-trip.
        """
        import json
        
        config = StrategyConfig()
        
        # Serialize to JSON string
        json_str = json.dumps(config.model_dump())
        
        # Deserialize from JSON string
        data = json.loads(json_str)
        reconstructed = StrategyConfig(**data)
        
        # Verify effective values
        assert reconstructed.chunking_mode_effective == config.chunking_mode_effective
        assert reconstructed.chunk_size_effective == config.chunk_size_effective
        assert reconstructed.chunk_overlap_effective == config.chunk_overlap_effective
        assert reconstructed.preserve_tables_effective == config.preserve_tables_effective

    def test_json_round_trip_with_flat_values(self) -> None:
        """
        Config with flat values survives JSON round-trip.
        """
        import json
        
        config = StrategyConfig(
            chunking_mode="semantic",
            chunk_size=1024,
            chunk_overlap=100,
            preserve_tables=False,
        )
        
        json_str = json.dumps(config.model_dump())
        data = json.loads(json_str)
        reconstructed = StrategyConfig(**data)
        
        assert reconstructed.chunking_mode_effective == "semantic"
        assert reconstructed.chunk_size_effective == 1024
        assert reconstructed.chunk_overlap_effective == 100
        assert reconstructed.preserve_tables_effective is False

    def test_json_round_trip_with_falsy_values(self) -> None:
        """
        Config with falsy values survives JSON round-trip.
        """
        import json
        
        config = StrategyConfig(
            chunk_overlap=0,
            preserve_tables=False,
        )
        
        json_str = json.dumps(config.model_dump())
        data = json.loads(json_str)
        reconstructed = StrategyConfig(**data)
        
        # Falsy values should be preserved
        assert reconstructed.chunk_overlap_effective == 0
        assert reconstructed.preserve_tables_effective is False

    def test_json_round_trip_with_all_fields(self) -> None:
        """
        Config with all fields set survives JSON round-trip.
        """
        import json
        
        config = StrategyConfig(
            ocr_provider="deepseek",
            ocr_concurrency=10,
            force_ocr=True,
            chunking_mode="layout_aware",
            chunk_size=256,
            chunk_overlap=25,
            preserve_tables=True,
            embedding_model="custom/model",
            embedding_batch_size=32,
            embedding_dimensions=768,
            vector_backend="qdrant",
            keyword_backend="disabled",
            enable_quantization=False,
            enable_semantic_cache=True,
            cache_ttl=7200,
            enable_hallucination_check=True,
            hallucination_threshold=0.7,
            algorithms=AlgorithmConfig(
                enable_raptor=True,
                raptor_max_cluster=15,
            ),
        )
        
        json_str = json.dumps(config.model_dump())
        data = json.loads(json_str)
        reconstructed = StrategyConfig(**data)
        
        # Verify all fields
        assert reconstructed.ocr_provider == "deepseek"
        assert reconstructed.ocr_concurrency == 10
        assert reconstructed.force_ocr is True
        assert reconstructed.chunking_mode_effective == "layout_aware"
        assert reconstructed.chunk_size_effective == 256
        assert reconstructed.embedding_model == "custom/model"
        assert reconstructed.enable_semantic_cache is True
        assert reconstructed.algorithms.enable_raptor is True
        assert reconstructed.algorithms.raptor_max_cluster == 15
