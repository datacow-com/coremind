"""
Property-based tests for KB Capability Configuration API

**Feature: capability-visualization, Property 1: KB Capability Configuration Round-Trip**
**Validates: Requirements 1.2, 12.1**

For any KB name and valid capability configuration, saving the configuration via PUT
and then retrieving it via GET should return an equivalent configuration.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any
from unittest.mock import patch, MagicMock
import json

from server.api.kb_config import (
    CapabilitySettings,
    KBCapabilityConfig,
    extract_capabilities_from_kb_config,
    merge_capabilities_to_kb_config,
    validate_capability_config,
    validate_all_capabilities,
    ValidationError,
)
from core.storage.kb_config import default_kb_config


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid KB names (alphanumeric with underscores, reasonable length)
kb_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=50,
).filter(lambda x: x[0].isalpha())  # Must start with letter

# Valid capability IDs from the manifest
VALID_CAPABILITY_IDS = [
    "basic.text_extraction",
    "basic.chunking",
    "basic.embedding",
    "enhanced.table_recognition",
    "enhanced.ocr",
    "enhanced.image_understanding",
    "enhanced.semantic_chunking",
    "enhanced.reranking",
    "pro.video_understanding",
    "pro.excel_analysis",
    "pro.comic_recognition",
    "pro.layout_analysis",
    "advanced.raptor",
    "advanced.graphrag",
]

capability_id_strategy = st.sampled_from(VALID_CAPABILITY_IDS)

# Valid config values for different types
config_value_strategy = st.one_of(
    st.booleans(),
    st.integers(min_value=0, max_value=10000),
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=50, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
    st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=5),
)

# Valid config keys (excluding reserved 'enabled' field)
config_key_strategy = st.text(
    min_size=1, max_size=20, 
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")
).filter(lambda x: x != "enabled")  # 'enabled' is a reserved field

# Valid capability settings
capability_settings_strategy = st.builds(
    CapabilitySettings,
    enabled=st.booleans(),
    config=st.dictionaries(
        keys=config_key_strategy,
        values=config_value_strategy,
        min_size=0,
        max_size=5,
    ),
)

# Valid KB capability config
kb_capability_config_strategy = st.builds(
    KBCapabilityConfig,
    capabilities=st.dictionaries(
        keys=capability_id_strategy,
        values=capability_settings_strategy,
        min_size=0,
        max_size=5,
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestKBCapabilityConfigRoundTrip:
    """
    **Feature: capability-visualization, Property 1: KB Capability Configuration Round-Trip**
    **Validates: Requirements 1.2, 12.1**
    
    For any KB name and valid capability configuration, saving the configuration via PUT
    and then retrieving it via GET should return an equivalent configuration.
    """

    @given(kb_name=kb_name_strategy, config=kb_capability_config_strategy)
    @settings(max_examples=100)
    def test_extract_merge_roundtrip(self, kb_name: str, config: KBCapabilityConfig):
        """
        Property: Extracting capabilities from KB config and merging them back
        should preserve the capability settings.
        """
        # Start with default KB config
        kb_config = default_kb_config(kb_name)
        
        # Merge the test capabilities into KB config
        merged_config = merge_capabilities_to_kb_config(kb_config.copy(), config.capabilities)
        
        # Extract capabilities back
        extracted = extract_capabilities_from_kb_config(merged_config)
        
        # Verify round-trip: all input capabilities should be present in output
        for cap_id, settings in config.capabilities.items():
            assert cap_id in extracted, f"Capability {cap_id} lost during round-trip"
            assert extracted[cap_id].enabled == settings.enabled, \
                f"Capability {cap_id} enabled state changed"
            
            # Config values should be preserved
            for key, value in settings.config.items():
                assert key in extracted[cap_id].config, \
                    f"Config key {key} lost for capability {cap_id}"
                assert extracted[cap_id].config[key] == value, \
                    f"Config value for {key} changed for capability {cap_id}"

    @given(kb_name=kb_name_strategy)
    @settings(max_examples=50)
    def test_default_config_extraction(self, kb_name: str):
        """
        Property: Extracting capabilities from default KB config should return
        a valid capability dictionary.
        """
        kb_config = default_kb_config(kb_name)
        extracted = extract_capabilities_from_kb_config(kb_config)
        
        # Should return a dictionary
        assert isinstance(extracted, dict)
        
        # All values should be CapabilitySettings
        for cap_id, settings in extracted.items():
            assert isinstance(settings, CapabilitySettings)
            assert isinstance(settings.enabled, bool)
            assert isinstance(settings.config, dict)

    @given(config=kb_capability_config_strategy)
    @settings(max_examples=50)
    def test_merge_preserves_other_fields(self, config: KBCapabilityConfig):
        """
        Property: Merging capabilities should not affect other KB config fields.
        """
        kb_config = default_kb_config("test_kb")
        original_name = kb_config.get("name")
        original_stack = kb_config.get("stack")
        original_top_k = kb_config.get("top_k_default")
        
        # Merge capabilities
        merged = merge_capabilities_to_kb_config(kb_config.copy(), config.capabilities)
        
        # Other fields should be preserved
        assert merged.get("name") == original_name
        assert merged.get("stack") == original_stack
        assert merged.get("top_k_default") == original_top_k

    @given(cap_id=capability_id_strategy, enabled=st.booleans())
    @settings(max_examples=50)
    def test_single_capability_roundtrip(self, cap_id: str, enabled: bool):
        """
        Property: A single capability setting should survive round-trip.
        """
        settings = CapabilitySettings(enabled=enabled, config={})
        capabilities = {cap_id: settings}
        
        kb_config = default_kb_config("test_kb")
        merged = merge_capabilities_to_kb_config(kb_config.copy(), capabilities)
        extracted = extract_capabilities_from_kb_config(merged)
        
        assert cap_id in extracted
        assert extracted[cap_id].enabled == enabled


class TestCapabilityValidation:
    """
    Tests for capability configuration validation.
    """

    def test_validate_unknown_capability(self):
        """Validating unknown capability should return error."""
        is_valid, errors = validate_capability_config("unknown.capability", {})
        
        assert not is_valid
        assert len(errors) == 1
        assert "Unknown capability" in errors[0].message

    def test_validate_empty_config_for_no_schema(self):
        """Capabilities without schema should accept empty config."""
        # text_extraction has no config_schema
        is_valid, errors = validate_capability_config("basic.text_extraction", {})
        
        assert is_valid
        assert len(errors) == 0

    @given(chunk_size=st.integers(min_value=128, max_value=2048))
    @settings(max_examples=20)
    def test_validate_chunking_valid_size(self, chunk_size: int):
        """Valid chunk sizes should pass validation."""
        config = {"chunk_size": chunk_size, "mode": "fixed", "overlap": 50}
        is_valid, errors = validate_capability_config("basic.chunking", config)
        
        # Should be valid if within range
        assert is_valid, f"Valid chunk_size {chunk_size} rejected: {errors}"

    @given(chunk_size=st.integers(max_value=127))
    @settings(max_examples=20)
    def test_validate_chunking_invalid_size_too_small(self, chunk_size: int):
        """Chunk sizes below minimum should fail validation."""
        config = {"chunk_size": chunk_size, "mode": "fixed", "overlap": 50}
        is_valid, errors = validate_capability_config("basic.chunking", config)
        
        # Should fail for sizes below minimum
        assert not is_valid
        assert any("chunk_size" in e.field for e in errors)

    @given(chunk_size=st.integers(min_value=2049))
    @settings(max_examples=20)
    def test_validate_chunking_invalid_size_too_large(self, chunk_size: int):
        """Chunk sizes above maximum should fail validation."""
        config = {"chunk_size": chunk_size, "mode": "fixed", "overlap": 50}
        is_valid, errors = validate_capability_config("basic.chunking", config)
        
        # Should fail for sizes above maximum
        assert not is_valid
        assert any("chunk_size" in e.field for e in errors)

    def test_validate_chunking_invalid_mode(self):
        """Invalid chunking mode should fail validation."""
        config = {"mode": "invalid_mode", "chunk_size": 512, "overlap": 50}
        is_valid, errors = validate_capability_config("basic.chunking", config)
        
        assert not is_valid
        assert any("mode" in e.field for e in errors)

    def test_validate_all_empty_capabilities(self):
        """Validating empty capabilities dict should succeed."""
        is_valid, errors = validate_all_capabilities({})
        
        assert is_valid
        assert len(errors) == 0

    @given(config=kb_capability_config_strategy)
    @settings(max_examples=30)
    def test_validate_all_returns_list(self, config: KBCapabilityConfig):
        """validate_all_capabilities should always return a list of errors."""
        is_valid, errors = validate_all_capabilities(config.capabilities)
        
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        for error in errors:
            assert isinstance(error, ValidationError)


class TestCapabilitySettingsModel:
    """Tests for CapabilitySettings Pydantic model."""

    def test_default_values(self):
        """CapabilitySettings should have sensible defaults."""
        settings = CapabilitySettings()
        
        assert settings.enabled is True
        assert settings.config == {}

    @given(enabled=st.booleans())
    @settings(max_examples=10)
    def test_enabled_preserved(self, enabled: bool):
        """Enabled flag should be preserved."""
        settings = CapabilitySettings(enabled=enabled)
        assert settings.enabled == enabled

    @given(config=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.integers(),
        min_size=0,
        max_size=5,
    ))
    @settings(max_examples=20)
    def test_config_preserved(self, config: dict):
        """Config dict should be preserved."""
        settings = CapabilitySettings(config=config)
        assert settings.config == config


class TestKBCapabilityConfigModel:
    """Tests for KBCapabilityConfig Pydantic model."""

    def test_default_values(self):
        """KBCapabilityConfig should have sensible defaults."""
        config = KBCapabilityConfig()
        
        assert config.capabilities == {}

    @given(config=kb_capability_config_strategy)
    @settings(max_examples=20)
    def test_model_serialization_roundtrip(self, config: KBCapabilityConfig):
        """Model should survive JSON serialization round-trip."""
        json_str = config.model_dump_json()
        restored = KBCapabilityConfig.model_validate_json(json_str)
        
        assert restored.capabilities.keys() == config.capabilities.keys()
        for cap_id in config.capabilities:
            assert restored.capabilities[cap_id].enabled == config.capabilities[cap_id].enabled
