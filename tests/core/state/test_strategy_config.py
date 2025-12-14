"""
StrategyConfig flat/nested compatibility tests.

Tests for Property 1 (flat config priority), default value behavior,
and Property 5 (invalid chunking_mode validation).
"""

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from core.state import ChunkingStrategy, StrategyConfig


# --- Hypothesis Strategies (P0/P1 Fix: ensure overlap < chunk_size) ---

CHUNKING_MODES = ["fixed", "semantic", "layout_aware", "table_first"]


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


# Alias for backward compatibility
chunking_strategy = valid_chunking_strategy()


# P0/P1 Fix: Generate valid flat config with overlap < chunk_size
@st.composite
def valid_flat_config(draw):
    """Generate flat config dict with valid overlap < chunk_size constraint."""
    chunking_mode = draw(st.sampled_from(CHUNKING_MODES))
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    # Ensure overlap < chunk_size
    chunk_overlap = draw(st.integers(min_value=0, max_value=chunk_size - 1))
    preserve_tables = draw(st.booleans())
    return {
        "chunking_mode": chunking_mode,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "preserve_tables": preserve_tables,
    }


# Alias for backward compatibility
flat_config = valid_flat_config()


class TestFlatConfigPriority:
    """
    **Feature: state-config-tests, Property 1: Flat config priority over nested**
    **Validates: Requirements 1.1, 1.3, 2.1-2.4**
    
    Tests that when both flat and nested chunking fields are provided,
    the effective properties return the flat values.
    """

    @settings(max_examples=100)
    @given(flat=flat_config, nested=chunking_strategy)
    def test_flat_config_priority_over_nested(
        self, flat: dict, nested: ChunkingStrategy
    ) -> None:
        """
        **Feature: state-config-tests, Property 1: Flat config priority over nested**
        **Validates: Requirements 1.1, 1.3, 2.1-2.4**
        
        For any valid flat configuration values and any valid nested ChunkingStrategy,
        when both are provided to StrategyConfig, the effective properties SHALL
        return the flat values.
        """
        # Create config with both flat and nested values
        config = StrategyConfig(
            chunking=nested,
            chunking_mode=flat["chunking_mode"],
            chunk_size=flat["chunk_size"],
            chunk_overlap=flat["chunk_overlap"],
            preserve_tables=flat["preserve_tables"],
        )

        # Verify effective properties return flat values
        assert config.chunking_mode_effective == flat["chunking_mode"], (
            f"Expected chunking_mode_effective={flat['chunking_mode']}, "
            f"got {config.chunking_mode_effective}"
        )
        assert config.chunk_size_effective == flat["chunk_size"], (
            f"Expected chunk_size_effective={flat['chunk_size']}, "
            f"got {config.chunk_size_effective}"
        )
        assert config.chunk_overlap_effective == flat["chunk_overlap"], (
            f"Expected chunk_overlap_effective={flat['chunk_overlap']}, "
            f"got {config.chunk_overlap_effective}"
        )
        assert config.preserve_tables_effective == flat["preserve_tables"], (
            f"Expected preserve_tables_effective={flat['preserve_tables']}, "
            f"got {config.preserve_tables_effective}"
        )


class TestNestedFallback:
    """
    **Feature: state-config-tests, Property 2: Nested fallback when flat is None**
    **Validates: Requirements 1.2, 2.1-2.4**
    
    Tests that when flat fields are all None, the effective properties
    return the nested ChunkingStrategy values.
    """

    @settings(max_examples=100)
    @given(nested=chunking_strategy)
    def test_nested_fallback_when_flat_is_none(
        self, nested: ChunkingStrategy
    ) -> None:
        """
        **Feature: state-config-tests, Property 2: Nested fallback when flat is None**
        **Validates: Requirements 1.2, 2.1-2.4**
        
        For any valid ChunkingStrategy, when flat fields are all None,
        the effective properties SHALL return the nested ChunkingStrategy values.
        """
        # Create config with only nested values (flat fields default to None)
        config = StrategyConfig(
            chunking=nested,
            # All flat fields are None (default)
            chunking_mode=None,
            chunk_size=None,
            chunk_overlap=None,
            preserve_tables=None,
        )

        # Verify effective properties return nested values
        assert config.chunking_mode_effective == nested.mode, (
            f"Expected chunking_mode_effective={nested.mode}, "
            f"got {config.chunking_mode_effective}"
        )
        assert config.chunk_size_effective == nested.chunk_size, (
            f"Expected chunk_size_effective={nested.chunk_size}, "
            f"got {config.chunk_size_effective}"
        )
        assert config.chunk_overlap_effective == nested.chunk_overlap, (
            f"Expected chunk_overlap_effective={nested.chunk_overlap}, "
            f"got {config.chunk_overlap_effective}"
        )
        assert config.preserve_tables_effective == nested.preserve_tables, (
            f"Expected preserve_tables_effective={nested.preserve_tables}, "
            f"got {config.preserve_tables_effective}"
        )

    def test_nested_only_config_uses_nested_values(self) -> None:
        """
        TC-1.2: When only nested chunking object is provided,
        the StrategyConfig SHALL use nested values for effective properties.
        
        Requirements: 1.2
        """
        nested = ChunkingStrategy(
            mode="semantic",
            chunk_size=1024,
            chunk_overlap=100,
            preserve_tables=False,
        )
        
        config = StrategyConfig(chunking=nested)
        
        assert config.chunking_mode_effective == "semantic"
        assert config.chunk_size_effective == 1024
        assert config.chunk_overlap_effective == 100
        assert config.preserve_tables_effective is False


class TestDefaultValues:
    """
    Tests for TC-1.4: Default StrategyConfig returns ChunkingStrategy defaults.
    
    Requirements: 1.4
    """

    def test_default_strategy_config_uses_chunking_defaults(self) -> None:
        """
        TC-1.4: When neither flat nor nested chunking fields are provided,
        the StrategyConfig SHALL use default values from ChunkingStrategy.
        
        Requirements: 1.4
        """
        # Create default config
        config = StrategyConfig()
        
        # Get ChunkingStrategy defaults
        default_chunking = ChunkingStrategy()

        # Verify effective properties match ChunkingStrategy defaults
        assert config.chunking_mode_effective == default_chunking.mode, (
            f"Expected default mode={default_chunking.mode}, "
            f"got {config.chunking_mode_effective}"
        )
        assert config.chunk_size_effective == default_chunking.chunk_size, (
            f"Expected default chunk_size={default_chunking.chunk_size}, "
            f"got {config.chunk_size_effective}"
        )
        assert config.chunk_overlap_effective == default_chunking.chunk_overlap, (
            f"Expected default chunk_overlap={default_chunking.chunk_overlap}, "
            f"got {config.chunk_overlap_effective}"
        )
        assert config.preserve_tables_effective == default_chunking.preserve_tables, (
            f"Expected default preserve_tables={default_chunking.preserve_tables}, "
            f"got {config.preserve_tables_effective}"
        )

    def test_default_values_are_expected(self) -> None:
        """
        Verify the actual default values match expected constants.
        
        Requirements: 1.4
        """
        config = StrategyConfig()
        
        # Verify specific default values
        assert config.chunking_mode_effective == "fixed"
        assert config.chunk_size_effective == 512
        assert config.chunk_overlap_effective == 50
        assert config.preserve_tables_effective is True


# --- Strategy for invalid chunking modes ---

# Generate strings that are NOT valid chunking modes
# Excludes: "fixed", "semantic", "layout_aware", "table_first"
invalid_chunking_mode = st.text(min_size=1, max_size=50).filter(
    lambda s: s not in CHUNKING_MODES
)


class TestInvalidChunkingModeValidation:
    """
    **Feature: state-config-tests, Property 5: Invalid chunking_mode raises validation error**
    **Validates: Requirements 5.1**
    
    Tests that invalid chunking_mode values raise Pydantic ValidationError.
    """

    @settings(max_examples=100)
    @given(invalid_mode=invalid_chunking_mode)
    def test_invalid_chunking_mode_raises_validation_error(
        self, invalid_mode: str
    ) -> None:
        """
        **Feature: state-config-tests, Property 5: Invalid chunking_mode raises validation error**
        **Validates: Requirements 5.1**
        
        For any string that is not in ["fixed", "semantic", "layout_aware", "table_first"],
        creating StrategyConfig with that chunking_mode SHALL raise a Pydantic ValidationError.
        """
        with pytest.raises(ValidationError):
            StrategyConfig(chunking_mode=invalid_mode)

    def test_specific_invalid_modes_raise_error(self) -> None:
        """
        TC-5.1: Test specific invalid chunking_mode values.
        
        Requirements: 5.1
        """
        invalid_modes = [
            "invalid",
            "FIXED",  # Case sensitive
            "Fixed",
            "semantic_chunking",
            "random",
            "123",
            " fixed",  # Leading space
            "fixed ",  # Trailing space
        ]
        
        for mode in invalid_modes:
            with pytest.raises(ValidationError):
                StrategyConfig(chunking_mode=mode)

    def test_valid_modes_do_not_raise_error(self) -> None:
        """
        Sanity check: valid modes should not raise errors.
        
        Requirements: 5.1
        """
        for mode in CHUNKING_MODES:
            # Should not raise
            config = StrategyConfig(chunking_mode=mode)
            assert config.chunking_mode == mode
