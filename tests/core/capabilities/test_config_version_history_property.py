"""
Property-based tests for Configuration Version History

**Feature: capability-visualization, Property 15: Configuration Version History**
**Validates: Requirements 12.3**

For any capability configuration update, the system should maintain a version history
entry with timestamp and previous value.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from typing import Any

from server.api.config_storage import (
    CapabilityConfig,
    ConfigExport,
    ConfigVersionEntry,
    InMemoryConfigStorage,
    StoredKBConfig,
    serialize_config,
    deserialize_config,
    pretty_print_config,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Strategies for generating test data
# ═══════════════════════════════════════════════════════════════════════════════

# Valid KB names (alphanumeric with underscores, reasonable length)
kb_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
    min_size=1,
    max_size=50,
).filter(lambda x: x[0].isalpha())  # Must start with letter

# Valid capability IDs
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
)

# Valid capability config
capability_config_strategy = st.builds(
    CapabilityConfig,
    enabled=st.booleans(),
    config=st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_")),
        values=config_value_strategy,
        min_size=0,
        max_size=3,
    ),
)

# Valid capabilities dict
capabilities_dict_strategy = st.dictionaries(
    keys=capability_id_strategy,
    values=capability_config_strategy,
    min_size=1,
    max_size=5,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests for Version History
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigVersionHistory:
    """
    **Feature: capability-visualization, Property 15: Configuration Version History**
    **Validates: Requirements 12.3**
    
    For any capability configuration update, the system should maintain a version
    history entry with timestamp and previous value.
    """

    @given(
        kb_name=kb_name_strategy,
        initial_caps=capabilities_dict_strategy,
        updated_caps=capabilities_dict_strategy,
    )
    @settings(max_examples=100)
    def test_version_history_created_on_update(
        self,
        kb_name: str,
        initial_caps: dict[str, CapabilityConfig],
        updated_caps: dict[str, CapabilityConfig],
    ):
        """
        Property: When configuration is updated, a version history entry should be
        created with the previous configuration.
        """
        storage = InMemoryConfigStorage()
        
        # Save initial config
        result1 = storage.save_config(kb_name, initial_caps)
        assert result1.version == 1
        
        # Save updated config
        result2 = storage.save_config(kb_name, updated_caps, changed_by="test_user")
        assert result2.version == 2
        
        # Check version history
        history = storage.get_version_history(kb_name)
        
        # Should have one history entry (the previous version)
        assert len(history) >= 1
        
        # The history entry should contain the previous version
        history_entry = history[0]
        assert history_entry.version == 1
        assert history_entry.created_at is not None

    @given(
        kb_name=kb_name_strategy,
        caps_list=st.lists(capabilities_dict_strategy, min_size=2, max_size=5),
    )
    @settings(max_examples=50)
    def test_version_increments_monotonically(
        self,
        kb_name: str,
        caps_list: list[dict[str, CapabilityConfig]],
    ):
        """
        Property: Version numbers should increment monotonically with each update.
        """
        storage = InMemoryConfigStorage()
        
        versions = []
        for caps in caps_list:
            result = storage.save_config(kb_name, caps)
            versions.append(result.version)
        
        # Versions should be strictly increasing
        for i in range(1, len(versions)):
            assert versions[i] > versions[i - 1], \
                f"Version did not increase: {versions[i-1]} -> {versions[i]}"
        
        # Versions should be consecutive
        for i, v in enumerate(versions):
            assert v == i + 1, f"Version {v} should be {i + 1}"

    @given(
        kb_name=kb_name_strategy,
        caps_list=st.lists(capabilities_dict_strategy, min_size=3, max_size=6),
    )
    @settings(max_examples=50)
    def test_history_preserves_all_versions(
        self,
        kb_name: str,
        caps_list: list[dict[str, CapabilityConfig]],
    ):
        """
        Property: All previous versions should be preserved in history.
        """
        storage = InMemoryConfigStorage()
        
        # Save multiple versions
        for caps in caps_list:
            storage.save_config(kb_name, caps)
        
        # Get history
        history = storage.get_version_history(kb_name, limit=100)
        
        # Should have n-1 history entries (all except current)
        assert len(history) == len(caps_list) - 1
        
        # History versions should be in descending order
        history_versions = [h.version for h in history]
        assert history_versions == sorted(history_versions, reverse=True)

    @given(
        kb_name=kb_name_strategy,
        initial_caps=capabilities_dict_strategy,
        updated_caps=capabilities_dict_strategy,
    )
    @settings(max_examples=50)
    def test_get_config_at_version(
        self,
        kb_name: str,
        initial_caps: dict[str, CapabilityConfig],
        updated_caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Should be able to retrieve configuration at any previous version.
        """
        storage = InMemoryConfigStorage()
        
        # Save initial and updated configs
        storage.save_config(kb_name, initial_caps)
        storage.save_config(kb_name, updated_caps)
        
        # Get config at version 1
        config_v1 = storage.get_config_at_version(kb_name, 1)
        assert config_v1 is not None
        assert config_v1.version == 1
        
        # Get config at version 2 (current)
        config_v2 = storage.get_config_at_version(kb_name, 2)
        assert config_v2 is not None
        assert config_v2.version == 2

    @given(kb_name=kb_name_strategy, version=st.integers(min_value=100, max_value=1000))
    @settings(max_examples=20)
    def test_get_nonexistent_version_returns_none(
        self,
        kb_name: str,
        version: int,
    ):
        """
        Property: Getting a non-existent version should return None.
        """
        storage = InMemoryConfigStorage()
        
        # No config saved yet
        result = storage.get_config_at_version(kb_name, version)
        assert result is None

    @given(
        kb_name=kb_name_strategy,
        caps=capabilities_dict_strategy,
        changed_by=st.text(min_size=1, max_size=50),
        change_reason=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=30)
    def test_history_preserves_metadata(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
        changed_by: str,
        change_reason: str,
    ):
        """
        Property: History entries should preserve changed_by and change_reason metadata.
        """
        storage = InMemoryConfigStorage()
        
        # Save initial config
        storage.save_config(kb_name, caps)
        
        # Save updated config with metadata
        storage.save_config(
            kb_name,
            caps,
            changed_by=changed_by,
            change_reason=change_reason,
        )
        
        # Check history
        history = storage.get_version_history(kb_name)
        assert len(history) >= 1
        
        # The history entry should have the metadata
        entry = history[0]
        assert entry.changed_by == changed_by
        assert entry.change_reason == change_reason


class TestConfigExportImport:
    """
    Tests for configuration export and import functionality.
    """

    @given(kb_name=kb_name_strategy, caps=capabilities_dict_strategy)
    @settings(max_examples=50)
    def test_export_contains_all_capabilities(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Exported config should contain all capability settings.
        """
        storage = InMemoryConfigStorage()
        storage.save_config(kb_name, caps)
        
        export = storage.export_config(kb_name)
        
        assert export is not None
        assert export.kb_name == kb_name
        assert set(export.capabilities.keys()) == set(caps.keys())
        
        for cap_id, cap_config in caps.items():
            assert export.capabilities[cap_id].enabled == cap_config.enabled
            assert export.capabilities[cap_id].config == cap_config.config

    @given(kb_name=kb_name_strategy, caps=capabilities_dict_strategy)
    @settings(max_examples=50)
    def test_import_replace_strategy(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Import with 'replace' strategy should replace all capabilities.
        """
        storage = InMemoryConfigStorage()
        
        # Save initial config
        initial_caps = {"basic.text_extraction": CapabilityConfig(enabled=True)}
        storage.save_config(kb_name, initial_caps)
        
        # Create export with different caps
        export = ConfigExport(
            kb_name=kb_name,
            version=1,
            capabilities=caps,
            exported_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # Import with replace
        result = storage.import_config(kb_name, export, merge_strategy="replace")
        
        # Should have only the imported capabilities
        assert set(result.capabilities.keys()) == set(caps.keys())

    @given(kb_name=kb_name_strategy)
    @settings(max_examples=20)
    def test_export_nonexistent_kb_returns_none(self, kb_name: str):
        """
        Property: Exporting non-existent KB should return None.
        """
        storage = InMemoryConfigStorage()
        export = storage.export_config(kb_name)
        assert export is None


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests for Serialization (Property 10)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigSerializationRoundTrip:
    """
    **Feature: capability-visualization, Property 10: Configuration Serialization Round-Trip**
    **Validates: Requirements 13.1, 13.2**
    
    For any valid capability configuration, serializing to JSON and deserializing
    should produce an equivalent configuration that passes schema validation.
    """

    @given(kb_name=kb_name_strategy, caps=capabilities_dict_strategy)
    @settings(max_examples=100)
    def test_serialization_roundtrip(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Serializing and deserializing should produce equivalent config.
        """
        storage = InMemoryConfigStorage()
        storage.save_config(kb_name, caps)
        
        config = storage.load_config(kb_name)
        assert config is not None
        
        # Serialize
        json_str = serialize_config(config)
        
        # Deserialize
        restored = deserialize_config(json_str)
        
        # Should be equivalent
        assert restored.kb_name == config.kb_name
        assert restored.version == config.version
        assert set(restored.capabilities.keys()) == set(config.capabilities.keys())
        
        for cap_id in config.capabilities:
            assert restored.capabilities[cap_id].enabled == config.capabilities[cap_id].enabled
            assert restored.capabilities[cap_id].config == config.capabilities[cap_id].config

    @given(kb_name=kb_name_strategy, caps=capabilities_dict_strategy)
    @settings(max_examples=50)
    def test_serialized_is_valid_json(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Serialized config should be valid JSON.
        """
        import json
        
        storage = InMemoryConfigStorage()
        storage.save_config(kb_name, caps)
        
        config = storage.load_config(kb_name)
        json_str = serialize_config(config)
        
        # Should be parseable as JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert "kb_name" in parsed
        assert "capabilities" in parsed

    @given(kb_name=kb_name_strategy, caps=capabilities_dict_strategy)
    @settings(max_examples=30)
    def test_pretty_print_contains_all_info(
        self,
        kb_name: str,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Pretty printed config should contain all capability info.
        """
        storage = InMemoryConfigStorage()
        storage.save_config(kb_name, caps)
        
        config = storage.load_config(kb_name)
        pretty = pretty_print_config(config)
        
        # Should contain KB name
        assert kb_name in pretty
        
        # Should contain all capability IDs
        for cap_id in caps:
            assert cap_id in pretty

    @given(caps=capabilities_dict_strategy)
    @settings(max_examples=30)
    def test_export_schema_version_present(
        self,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Exported config should have schema_version field.
        """
        storage = InMemoryConfigStorage()
        storage.save_config("test_kb", caps)
        
        export = storage.export_config("test_kb")
        
        assert export is not None
        assert export.schema_version is not None
        assert export.schema_version == "1.0"

    @given(caps=capabilities_dict_strategy)
    @settings(max_examples=30)
    def test_export_timestamp_present(
        self,
        caps: dict[str, CapabilityConfig],
    ):
        """
        Property: Exported config should have exported_at timestamp.
        """
        storage = InMemoryConfigStorage()
        storage.save_config("test_kb", caps)
        
        export = storage.export_config("test_kb")
        
        assert export is not None
        assert export.exported_at is not None
        assert len(export.exported_at) > 0
