"""
Effective properties boundary case tests.

Tests for Property 3: Falsy values are not treated as unset.
"""

import pytest
from hypothesis import given, settings, strategies as st

from core.state import ChunkingStrategy, StrategyConfig


# --- Hypothesis Strategies ---

CHUNKING_MODES = ["fixed", "semantic", "layout_aware", "table_first"]

# P0/P1 Fix: ChunkingStrategy generator with non-zero overlap and True preserve_tables
# to ensure nested values differ from falsy flat values, with overlap < chunk_size
@st.composite
def valid_chunking_strategy_non_falsy(draw):
    """Generate ChunkingStrategy with non-zero overlap < chunk_size."""
    mode = draw(st.sampled_from(CHUNKING_MODES))
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    # Ensure overlap is non-zero AND less than chunk_size
    chunk_overlap = draw(st.integers(min_value=1, max_value=max(1, chunk_size - 1)))
    return ChunkingStrategy(
        mode=mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        preserve_tables=True,  # Always True to contrast with False flat value
    )


chunking_strategy_non_falsy = valid_chunking_strategy_non_falsy()


class TestFalsyValuesNotTreatedAsUnset:
    """
    **Feature: state-config-tests, Property 3: Falsy values are not treated as unset**
    **Validates: Requirements 2.5**
    
    Tests that when flat fields are explicitly set to falsy but valid values
    (e.g., chunk_overlap=0, preserve_tables=False), the effective properties
    return those values, not the nested defaults.
    """

    @settings(max_examples=100)
    @given(nested=chunking_strategy_non_falsy)
    def test_chunk_overlap_zero_is_not_treated_as_unset(
        self, nested: ChunkingStrategy
    ) -> None:
        """
        **Feature: state-config-tests, Property 3: Falsy values are not treated as unset**
        **Validates: Requirements 2.5**
        
        For any StrategyConfig where flat chunk_overlap is explicitly 0,
        the chunk_overlap_effective SHALL return 0, not the nested default.
        """
        # Ensure nested has non-zero overlap
        assert nested.chunk_overlap > 0, "Test setup: nested overlap must be > 0"
        
        # Create config with flat chunk_overlap=0 and nested with non-zero overlap
        config = StrategyConfig(
            chunking=nested,
            chunk_overlap=0,  # Explicitly set to falsy value
        )

        # Verify effective returns 0, not nested value
        assert config.chunk_overlap_effective == 0, (
            f"Expected chunk_overlap_effective=0 (flat value), "
            f"got {config.chunk_overlap_effective} (nested={nested.chunk_overlap})"
        )

    @settings(max_examples=100)
    @given(nested=chunking_strategy_non_falsy)
    def test_preserve_tables_false_is_not_treated_as_unset(
        self, nested: ChunkingStrategy
    ) -> None:
        """
        **Feature: state-config-tests, Property 3: Falsy values are not treated as unset**
        **Validates: Requirements 2.5**
        
        For any StrategyConfig where flat preserve_tables is explicitly False,
        the preserve_tables_effective SHALL return False, not the nested default.
        """
        # Ensure nested has preserve_tables=True
        assert nested.preserve_tables is True, "Test setup: nested preserve_tables must be True"
        
        # Create config with flat preserve_tables=False and nested with True
        config = StrategyConfig(
            chunking=nested,
            preserve_tables=False,  # Explicitly set to falsy value
        )

        # Verify effective returns False, not nested value
        assert config.preserve_tables_effective is False, (
            f"Expected preserve_tables_effective=False (flat value), "
            f"got {config.preserve_tables_effective} (nested={nested.preserve_tables})"
        )


class TestFalsyValuesBoundaryExamples:
    """
    Unit tests for specific boundary cases with falsy values.
    
    TC-2.1, TC-2.2, TC-2.3 from design document.
    Requirements: 2.5
    """

    def test_chunk_overlap_zero_example(self) -> None:
        """
        TC-2.1: chunk_overlap=0 should return chunk_overlap_effective == 0.
        
        Requirements: 2.5
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(chunk_overlap=100),  # Nested has 100
            chunk_overlap=0,  # Flat is 0
        )
        
        assert config.chunk_overlap_effective == 0

    def test_preserve_tables_false_example(self) -> None:
        """
        TC-2.2: preserve_tables=False should return preserve_tables_effective == False.
        
        Requirements: 2.5
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(preserve_tables=True),  # Nested is True
            preserve_tables=False,  # Flat is False
        )
        
        assert config.preserve_tables_effective is False

    def test_chunk_size_minimum_example(self) -> None:
        """
        TC-2.3: chunk_size=1 (minimum valid) should return chunk_size_effective == 1.
        
        Note: chunk_size must be > 0 after P0 fix.
        
        Requirements: 2.5
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(chunk_size=512, chunk_overlap=0),  # Nested has 512
            chunk_size=1,  # Flat is 1 (minimum valid)
            chunk_overlap=0,  # Must be < chunk_size
        )
        
        # The effective value should be 1 (flat value), not 512 (nested)
        assert config.chunk_size_effective == 1


# --- Hypothesis Strategies for Serialization Round-Trip ---

# P0/P1 Fix: Generate valid ChunkingStrategy with overlap < chunk_size
@st.composite
def valid_chunking_strategy(draw):
    """Generate ChunkingStrategy with valid overlap < chunk_size constraint."""
    mode = draw(st.sampled_from(CHUNKING_MODES))
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    # Ensure overlap < chunk_size
    chunk_overlap = draw(st.integers(min_value=0, max_value=chunk_size - 1))
    preserve_tables = draw(st.booleans())
    return ChunkingStrategy(
        mode=mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        preserve_tables=preserve_tables,
    )


# P0/P1 Fix: Generate valid StrategyConfig with overlap < chunk_size constraint
@st.composite
def valid_strategy_config(draw):
    """Generate StrategyConfig with valid overlap < chunk_size constraint."""
    chunking = draw(valid_chunking_strategy())
    chunking_mode = draw(st.one_of(st.none(), st.sampled_from(CHUNKING_MODES)))
    
    # For flat fields, ensure overlap < chunk_size when both are set
    flat_chunk_size = draw(st.one_of(st.none(), st.integers(min_value=64, max_value=4096)))
    if flat_chunk_size is not None:
        flat_chunk_overlap = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=flat_chunk_size - 1)))
    else:
        flat_chunk_overlap = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=512)))
    
    preserve_tables = draw(st.one_of(st.none(), st.booleans()))
    
    return StrategyConfig(
        chunking=chunking,
        chunking_mode=chunking_mode,
        chunk_size=flat_chunk_size,
        chunk_overlap=flat_chunk_overlap,
        preserve_tables=preserve_tables,
    )


# Alias for backward compatibility
strategy_config_full = valid_strategy_config()


class TestSerializationRoundTrip:
    """
    **Feature: state-config-tests, Property 4: Serialization round-trip preserves effective values**
    **Validates: Requirements 5.4**
    
    Tests that serializing StrategyConfig to dict via model_dump() and
    reconstructing it preserves all effective property values.
    """

    @settings(max_examples=100)
    @given(config=strategy_config_full)
    def test_serialization_round_trip_preserves_effective_values(
        self, config: StrategyConfig
    ) -> None:
        """
        **Feature: state-config-tests, Property 4: Serialization round-trip preserves effective values**
        **Validates: Requirements 5.4**
        
        For any valid StrategyConfig, serializing to dict via model_dump()
        and reconstructing SHALL preserve all effective property values.
        """
        # Capture original effective values
        original_mode = config.chunking_mode_effective
        original_size = config.chunk_size_effective
        original_overlap = config.chunk_overlap_effective
        original_preserve = config.preserve_tables_effective

        # Serialize to dict
        serialized = config.model_dump()

        # Reconstruct from dict
        reconstructed = StrategyConfig(**serialized)

        # Verify all effective values are preserved
        assert reconstructed.chunking_mode_effective == original_mode, (
            f"chunking_mode_effective changed: {original_mode} -> {reconstructed.chunking_mode_effective}"
        )
        assert reconstructed.chunk_size_effective == original_size, (
            f"chunk_size_effective changed: {original_size} -> {reconstructed.chunk_size_effective}"
        )
        assert reconstructed.chunk_overlap_effective == original_overlap, (
            f"chunk_overlap_effective changed: {original_overlap} -> {reconstructed.chunk_overlap_effective}"
        )
        assert reconstructed.preserve_tables_effective == original_preserve, (
            f"preserve_tables_effective changed: {original_preserve} -> {reconstructed.preserve_tables_effective}"
        )

    @settings(max_examples=100)
    @given(config=strategy_config_full)
    def test_serialization_round_trip_preserves_raw_fields(
        self, config: StrategyConfig
    ) -> None:
        """
        **Feature: state-config-tests, Property 4: Serialization round-trip preserves effective values**
        **Validates: Requirements 5.4**
        
        For any valid StrategyConfig, serializing and reconstructing
        SHALL preserve both flat and nested field values exactly.
        """
        # Serialize to dict
        serialized = config.model_dump()

        # Reconstruct from dict
        reconstructed = StrategyConfig(**serialized)

        # Verify flat fields are preserved
        assert reconstructed.chunking_mode == config.chunking_mode
        assert reconstructed.chunk_size == config.chunk_size
        assert reconstructed.chunk_overlap == config.chunk_overlap
        assert reconstructed.preserve_tables == config.preserve_tables

        # Verify nested fields are preserved
        assert reconstructed.chunking.mode == config.chunking.mode
        assert reconstructed.chunking.chunk_size == config.chunking.chunk_size
        assert reconstructed.chunking.chunk_overlap == config.chunking.chunk_overlap
        assert reconstructed.chunking.preserve_tables == config.chunking.preserve_tables


class TestSerializationRoundTripExamples:
    """
    Unit tests for specific serialization round-trip cases.
    
    TC-5.3 from design document.
    Requirements: 5.4
    """

    def test_round_trip_with_flat_only(self) -> None:
        """
        TC-5.3: Serialization round-trip with flat fields only.
        
        Requirements: 5.4
        """
        config = StrategyConfig(
            chunking_mode="semantic",
            chunk_size=1024,
            chunk_overlap=100,
            preserve_tables=False,
        )

        serialized = config.model_dump()
        reconstructed = StrategyConfig(**serialized)

        assert reconstructed.chunking_mode_effective == "semantic"
        assert reconstructed.chunk_size_effective == 1024
        assert reconstructed.chunk_overlap_effective == 100
        assert reconstructed.preserve_tables_effective is False

    def test_round_trip_with_nested_only(self) -> None:
        """
        TC-5.3: Serialization round-trip with nested fields only.
        
        Requirements: 5.4
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(
                mode="layout_aware",
                chunk_size=256,
                chunk_overlap=25,
                preserve_tables=True,
            )
        )

        serialized = config.model_dump()
        reconstructed = StrategyConfig(**serialized)

        assert reconstructed.chunking_mode_effective == "layout_aware"
        assert reconstructed.chunk_size_effective == 256
        assert reconstructed.chunk_overlap_effective == 25
        assert reconstructed.preserve_tables_effective is True

    def test_round_trip_with_mixed_fields(self) -> None:
        """
        TC-5.3: Serialization round-trip with both flat and nested fields.
        
        Requirements: 5.4
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(
                mode="fixed",
                chunk_size=512,
                chunk_overlap=50,
                preserve_tables=True,
            ),
            chunking_mode="semantic",
            chunk_size=1024,
            chunk_overlap=100,
            preserve_tables=False,
        )

        serialized = config.model_dump()
        reconstructed = StrategyConfig(**serialized)

        # Flat values should take priority
        assert reconstructed.chunking_mode_effective == "semantic"
        assert reconstructed.chunk_size_effective == 1024
        assert reconstructed.chunk_overlap_effective == 100
        assert reconstructed.preserve_tables_effective is False

    def test_round_trip_with_falsy_flat_values(self) -> None:
        """
        TC-5.3: Serialization round-trip preserves falsy flat values.
        
        Note: chunk_size must be > 0 after P0 fix, so we use minimum valid value (1).
        chunk_overlap=0 is still valid (no overlap).
        
        Requirements: 5.4
        """
        config = StrategyConfig(
            chunking=ChunkingStrategy(
                chunk_size=512,
                chunk_overlap=50,
                preserve_tables=True,
            ),
            chunk_size=1,  # P0 Fix: minimum valid value (was 0)
            chunk_overlap=0,  # Still valid (no overlap)
            preserve_tables=False,
        )

        serialized = config.model_dump()
        reconstructed = StrategyConfig(**serialized)

        # Falsy flat values should be preserved
        assert reconstructed.chunk_size_effective == 1  # P0 Fix: minimum valid value
        assert reconstructed.chunk_overlap_effective == 0
        assert reconstructed.preserve_tables_effective is False
