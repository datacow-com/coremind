"""
Property-based tests for channel naming convention.

**Feature: real-e2e-tests, Property 15: Channel Naming Convention**
**Validates: Requirements 3.1**

Tests that channel_utils generates correct prefixed names following
the pattern "{channel_id}_{base_name}".
"""

import re

import pytest
from hypothesis import given, settings, strategies as st

from core.storage.channel_utils import (
    channel_blob_prefix,
    channel_collection_name,
    channel_index_name,
    parse_channel_from_collection,
)


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Valid channel_id: alphanumeric with underscores, 1-50 chars
# Avoid leading/trailing underscores and consecutive underscores
valid_channel_id = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
    min_size=1,
    max_size=50,
)

# Valid kb_name: alphanumeric with underscores, 1-50 chars
valid_kb_name = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
    min_size=1,
    max_size=50,
)

# Valid version: positive integers
valid_version = st.integers(min_value=1, max_value=1000)


# =============================================================================
# Property Tests
# =============================================================================


class TestChannelNamingConventionProperty:
    """
    **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
    **Validates: Requirements 3.1**
    
    For any channel_id, the generated collection name should follow
    the pattern "{channel_id}_{base_name}" where base_name is the
    configured collection name.
    """

    @settings(max_examples=100)
    @given(
        channel_id=valid_channel_id,
        kb_name=valid_kb_name,
        version=valid_version,
    )
    def test_collection_name_contains_channel_prefix(
        self,
        channel_id: str,
        kb_name: str,
        version: int,
    ) -> None:
        """
        **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
        **Validates: Requirements 3.1**
        
        For any valid channel_id, kb_name, and version, the generated
        collection name SHALL start with "ch_{channel_id}_".
        """
        collection_name = channel_collection_name(channel_id, kb_name, version)
        
        # Property: Collection name starts with channel prefix
        expected_prefix = f"ch_{channel_id}_"
        assert collection_name.startswith(expected_prefix), (
            f"Collection name '{collection_name}' should start with '{expected_prefix}'"
        )
        
        # Property: Collection name contains kb_name
        assert f"kb_{kb_name}" in collection_name, (
            f"Collection name '{collection_name}' should contain 'kb_{kb_name}'"
        )
        
        # Property: Collection name ends with version
        assert collection_name.endswith(f"_v{version}"), (
            f"Collection name '{collection_name}' should end with '_v{version}'"
        )

    @settings(max_examples=100)
    @given(
        channel_id=valid_channel_id,
        kb_name=valid_kb_name,
    )
    def test_index_name_contains_channel_prefix(
        self,
        channel_id: str,
        kb_name: str,
    ) -> None:
        """
        **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
        **Validates: Requirements 3.1**
        
        For any valid channel_id and kb_name, the generated index name
        SHALL start with "ch_{channel_id}_".
        """
        index_name = channel_index_name(channel_id, kb_name)
        
        # Property: Index name starts with channel prefix
        expected_prefix = f"ch_{channel_id}_"
        assert index_name.startswith(expected_prefix), (
            f"Index name '{index_name}' should start with '{expected_prefix}'"
        )
        
        # Property: Index name contains kb_name
        assert f"kb_{kb_name}" in index_name, (
            f"Index name '{index_name}' should contain 'kb_{kb_name}'"
        )
        
        # Property: Index name ends with _docs
        assert index_name.endswith("_docs"), (
            f"Index name '{index_name}' should end with '_docs'"
        )

    @settings(max_examples=100)
    @given(
        channel_id=valid_channel_id,
        kb_name=valid_kb_name,
    )
    def test_blob_prefix_contains_channel_path(
        self,
        channel_id: str,
        kb_name: str,
    ) -> None:
        """
        **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
        **Validates: Requirements 3.1**
        
        For any valid channel_id and kb_name, the generated blob prefix
        SHALL contain "channels/{channel_id}/".
        """
        blob_prefix = channel_blob_prefix(channel_id, kb_name)
        
        # Property: Blob prefix starts with channels/{channel_id}/
        expected_start = f"channels/{channel_id}/"
        assert blob_prefix.startswith(expected_start), (
            f"Blob prefix '{blob_prefix}' should start with '{expected_start}'"
        )
        
        # Property: Blob prefix contains kb/{kb_name}/
        assert f"kb/{kb_name}/" in blob_prefix, (
            f"Blob prefix '{blob_prefix}' should contain 'kb/{kb_name}/'"
        )
        
        # Property: Blob prefix ends with /
        assert blob_prefix.endswith("/"), (
            f"Blob prefix '{blob_prefix}' should end with '/'"
        )


class TestChannelNamingRoundTrip:
    """
    **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
    **Validates: Requirements 3.1**
    
    Tests that collection names can be parsed back to extract the
    original channel_id, kb_name, and version.
    """

    @settings(max_examples=100)
    @given(
        channel_id=valid_channel_id,
        kb_name=valid_kb_name,
        version=valid_version,
    )
    def test_collection_name_round_trip(
        self,
        channel_id: str,
        kb_name: str,
        version: int,
    ) -> None:
        """
        **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
        **Validates: Requirements 3.1**
        
        For any valid channel_id, kb_name, and version, generating a
        collection name and parsing it back SHALL return the original values.
        """
        # Generate collection name
        collection_name = channel_collection_name(channel_id, kb_name, version)
        
        # Parse it back
        parsed_channel, parsed_kb, parsed_version = parse_channel_from_collection(
            collection_name
        )
        
        # Property: Round-trip preserves channel_id
        assert parsed_channel == channel_id, (
            f"Parsed channel '{parsed_channel}' should equal original '{channel_id}'"
        )
        
        # Property: Round-trip preserves kb_name
        assert parsed_kb == kb_name, (
            f"Parsed kb_name '{parsed_kb}' should equal original '{kb_name}'"
        )
        
        # Property: Round-trip preserves version
        assert parsed_version == version, (
            f"Parsed version '{parsed_version}' should equal original '{version}'"
        )


class TestLegacyNamingFallback:
    """
    Tests for legacy naming (no channel_id) fallback behavior.
    """

    @settings(max_examples=100)
    @given(
        kb_name=valid_kb_name,
        version=valid_version,
    )
    def test_legacy_collection_name_no_channel_prefix(
        self,
        kb_name: str,
        version: int,
    ) -> None:
        """
        For any valid kb_name and version with no channel_id,
        the generated collection name SHALL NOT contain channel prefix.
        """
        collection_name = channel_collection_name(None, kb_name, version)
        
        # Property: Legacy collection name does NOT start with "ch_"
        assert not collection_name.startswith("ch_"), (
            f"Legacy collection name '{collection_name}' should not start with 'ch_'"
        )
        
        # Property: Legacy collection name starts with "kb_"
        assert collection_name.startswith("kb_"), (
            f"Legacy collection name '{collection_name}' should start with 'kb_'"
        )

    @settings(max_examples=100)
    @given(
        kb_name=valid_kb_name,
    )
    def test_legacy_index_name_no_channel_prefix(
        self,
        kb_name: str,
    ) -> None:
        """
        For any valid kb_name with no channel_id,
        the generated index name SHALL NOT contain channel prefix.
        """
        index_name = channel_index_name(None, kb_name)
        
        # Property: Legacy index name does NOT start with "ch_"
        assert not index_name.startswith("ch_"), (
            f"Legacy index name '{index_name}' should not start with 'ch_'"
        )
        
        # Property: Legacy index name starts with "kb_"
        assert index_name.startswith("kb_"), (
            f"Legacy index name '{index_name}' should start with 'kb_'"
        )


class TestChannelIsolation:
    """
    Tests that different channels produce different collection/index names.
    """

    @settings(max_examples=100)
    @given(
        channel_a=valid_channel_id,
        channel_b=valid_channel_id,
        kb_name=valid_kb_name,
        version=valid_version,
    )
    def test_different_channels_produce_different_collection_names(
        self,
        channel_a: str,
        channel_b: str,
        kb_name: str,
        version: int,
    ) -> None:
        """
        For any two different channel_ids with the same kb_name and version,
        the generated collection names SHALL be different.
        """
        # Skip if channels are the same
        if channel_a == channel_b:
            return
        
        collection_a = channel_collection_name(channel_a, kb_name, version)
        collection_b = channel_collection_name(channel_b, kb_name, version)
        
        # Property: Different channels produce different collection names
        assert collection_a != collection_b, (
            f"Collections for different channels should differ: "
            f"'{collection_a}' vs '{collection_b}'"
        )

    @settings(max_examples=100)
    @given(
        channel_a=valid_channel_id,
        channel_b=valid_channel_id,
        kb_name=valid_kb_name,
    )
    def test_different_channels_produce_different_index_names(
        self,
        channel_a: str,
        channel_b: str,
        kb_name: str,
    ) -> None:
        """
        For any two different channel_ids with the same kb_name,
        the generated index names SHALL be different.
        """
        # Skip if channels are the same
        if channel_a == channel_b:
            return
        
        index_a = channel_index_name(channel_a, kb_name)
        index_b = channel_index_name(channel_b, kb_name)
        
        # Property: Different channels produce different index names
        assert index_a != index_b, (
            f"Indexes for different channels should differ: "
            f"'{index_a}' vs '{index_b}'"
        )
