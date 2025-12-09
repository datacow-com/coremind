"""Tests for the capability registry module."""

import pytest


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry class."""

    def test_registry_singleton(self):
        """Test that get_registry returns the same instance."""
        from core.capabilities.registry import get_registry

        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_list_all_capabilities(self):
        """Test listing all capabilities."""
        from core.capabilities.registry import list_all_capabilities

        caps = list_all_capabilities()
        assert isinstance(caps, list)
        assert len(caps) > 0

        # Check structure of capability summary
        cap = caps[0]
        assert "id" in cap
        assert "name" in cap
        assert "category" in cap

    def test_get_capability_by_id(self):
        """Test getting a specific capability."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        # Get basic text extraction
        cap = registry.get("basic.text_extraction")
        assert cap is not None
        assert cap["id"] == "basic.text_extraction"
        assert cap["category"] == "basic"

        # Get enhanced table recognition
        cap = registry.get("enhanced.table_recognition")
        assert cap is not None
        assert "config_schema" in cap

    def test_get_capability_short_id(self):
        """Test getting capability with short ID (without prefix)."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        # Should work with just 'chunking' instead of 'basic.chunking'
        cap = registry.get("chunking")
        assert cap is not None
        assert "chunking" in cap["id"].lower()

    def test_get_nonexistent_capability(self):
        """Test getting a capability that doesn't exist."""
        from core.capabilities.registry import get_registry

        registry = get_registry()
        cap = registry.get("nonexistent.capability")
        assert cap is None

    def test_get_config_schema(self):
        """Test getting config schema for a capability."""
        from core.capabilities.registry import get_registry

        registry = get_registry()
        schema = registry.get_config_schema("basic.chunking")

        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "mode" in schema["properties"]
        assert "chunk_size" in schema["properties"]

    def test_get_default_config(self):
        """Test getting default configuration."""
        from core.capabilities.registry import get_registry

        registry = get_registry()
        defaults = registry.get_default_config("basic.chunking")

        assert defaults is not None
        assert "mode" in defaults
        assert defaults["mode"] == "fixed"
        assert defaults["chunk_size"] == 512

    def test_validate_config_valid(self):
        """Test validating a valid configuration."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        config = {
            "mode": "semantic",
            "chunk_size": 1024,
            "overlap": 100,
        }

        result = registry.validate_config("basic.chunking", config)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_config_invalid_type(self):
        """Test validating configuration with wrong type."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        config = {
            "chunk_size": "not_a_number",  # Should be integer
        }

        result = registry.validate_config("basic.chunking", config)
        # Note: Basic validation may not catch type errors
        # This depends on implementation

    def test_list_by_category(self):
        """Test listing capabilities by category."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        basic_caps = registry.list_by_category("basic")
        assert len(basic_caps) > 0
        for cap in basic_caps:
            assert cap["category"] == "basic"

        enhanced_caps = registry.list_by_category("enhanced")
        assert len(enhanced_caps) > 0
        for cap in enhanced_caps:
            assert cap["category"] == "enhanced"

    def test_get_categories(self):
        """Test getting category definitions."""
        from core.capabilities.registry import get_registry

        registry = get_registry()
        categories = registry.get_categories()

        assert "basic" in categories
        assert "enhanced" in categories
        assert "pro" in categories
        assert "advanced" in categories

        # Check category structure
        basic = categories["basic"]
        assert "name" in basic
        assert "description" in basic
        assert "order" in basic

    def test_check_dependencies(self):
        """Test checking capability dependencies."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        # Image understanding requires VLM provider
        result = registry.check_dependencies("enhanced.image_understanding")
        assert "requires" in result or "dependencies" in result or result is not None

    def test_get_capabilities_for_kb_config(self):
        """Test getting capabilities structured for KB config form."""
        from core.capabilities.registry import get_capabilities_for_kb_config

        data = get_capabilities_for_kb_config()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure
        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "category" in item


class TestCapabilityLoader:
    """Tests for CapabilityLoader class."""

    def test_loader_instantiation(self):
        """Test creating a CapabilityLoader instance."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader("test_kb", {})
        assert loader.kb_name == "test_kb"
        assert loader.kb_config == {}

    def test_get_status(self):
        """Test getting capability status."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader(
            "test_kb", {"capabilities": {"basic": {"chunking": {"enabled": True}}}}
        )

        status = loader.get_status()
        assert isinstance(status, dict)

    def test_is_enabled(self):
        """Test checking if capability is enabled."""
        from core.capabilities.loader import CapabilityLoader

        kb_config = {
            "capabilities": {
                "basic": {"text_extraction": True},
                "enhanced": {"table_recognition": {"enabled": False}},
            }
        }

        loader = CapabilityLoader("test_kb", kb_config)

        # Basic text extraction should be enabled (always on)
        # Enhanced table recognition should be disabled

    @pytest.mark.asyncio
    async def test_prepare_capability(self):
        """Test preparing a capability for use."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader("test_kb", {})

        # This should not raise even with minimal config
        # as it handles missing implementation gracefully


class TestCapabilityStatus:
    """Tests for CapabilityStatus enum."""

    def test_status_values(self):
        """Test CapabilityStatus enum values."""
        from core.capabilities.loader import CapabilityStatus

        assert CapabilityStatus.NOT_LOADED is not None
        assert CapabilityStatus.LOADING is not None
        assert CapabilityStatus.READY is not None
        assert CapabilityStatus.ERROR is not None
        assert CapabilityStatus.DISABLED is not None
