"""Tests for core.storage.channel_utils module."""

import pytest

from core.storage.channel_utils import (
    channel_blob_prefix,
    channel_collection_name,
    channel_index_name,
    parse_channel_from_collection,
    validate_channel_access,
)


class TestChannelCollectionName:
    """Tests for channel_collection_name function."""

    @pytest.mark.unit
    def test_with_channel_id(self):
        """Test collection name with channel ID."""
        result = channel_collection_name("ch1", "legal", 2)
        assert result == "ch_ch1_kb_legal_v2"

    @pytest.mark.unit
    def test_without_channel_id(self):
        """Test collection name without channel ID (legacy)."""
        result = channel_collection_name(None, "legal", 1)
        assert result == "kb_legal_v1"

    @pytest.mark.unit
    def test_default_version(self):
        """Test with default version."""
        result = channel_collection_name("ch1", "docs", 1)
        assert result == "ch_ch1_kb_docs_v1"


class TestChannelIndexName:
    """Tests for channel_index_name function."""

    @pytest.mark.unit
    def test_with_channel_id(self):
        """Test index name with channel ID."""
        result = channel_index_name("ch1", "legal")
        assert result == "ch_ch1_kb_legal_docs"

    @pytest.mark.unit
    def test_without_channel_id(self):
        """Test index name without channel ID (legacy)."""
        result = channel_index_name(None, "legal")
        assert result == "kb_legal_docs"


class TestChannelBlobPrefix:
    """Tests for channel_blob_prefix function."""

    @pytest.mark.unit
    def test_with_channel_id(self):
        """Test blob prefix with channel ID."""
        result = channel_blob_prefix("ch1", "legal")
        assert result == "channels/ch1/kb/legal/"

    @pytest.mark.unit
    def test_without_channel_id(self):
        """Test blob prefix without channel ID (legacy)."""
        result = channel_blob_prefix(None, "legal")
        assert result == "kb/legal/"


class TestParseChannelFromCollection:
    """Tests for parse_channel_from_collection function."""

    @pytest.mark.unit
    def test_parse_channel_collection(self):
        """Test parsing collection with channel."""
        channel, kb, version = parse_channel_from_collection("ch_ch1_kb_legal_v2")
        assert channel == "ch1"
        assert kb == "legal"
        assert version == 2

    @pytest.mark.unit
    def test_parse_legacy_collection(self):
        """Test parsing legacy collection without channel."""
        channel, kb, version = parse_channel_from_collection("kb_legal_v1")
        assert channel is None
        assert kb == "legal"
        assert version == 1

    @pytest.mark.unit
    def test_parse_unknown_format(self):
        """Test parsing unknown collection format."""
        channel, kb, version = parse_channel_from_collection("random_name")
        assert channel is None
        assert kb == "random_name"
        assert version == 1


class TestValidateChannelAccess:
    """Tests for validate_channel_access function."""

    @pytest.mark.unit
    def test_matching_channel(self):
        """Test access with matching channel."""
        result = validate_channel_access("ch1", "ch_ch1_kb_legal_v1", strict=False)
        assert result is True

    @pytest.mark.unit
    def test_mismatched_channel(self):
        """Test access with mismatched channel."""
        result = validate_channel_access("ch2", "ch_ch1_kb_legal_v1", strict=False)
        assert result is False

    @pytest.mark.unit
    def test_legacy_collection_always_allowed(self):
        """Test legacy collections are always accessible."""
        result = validate_channel_access("ch1", "kb_legal_v1", strict=False)
        assert result is True

    @pytest.mark.unit
    def test_strict_mode_raises(self):
        """Test strict mode raises PermissionError."""
        with pytest.raises(PermissionError):
            validate_channel_access("ch2", "ch_ch1_kb_legal_v1", strict=True)
