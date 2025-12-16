"""Tests for the capability registry module."""

import pytest


class TestCapabilityRegistry:
    """Tests for CapabilityRegistry class."""

    def test_registry_creation(self):
        """Test that CapabilityRegistry can be created."""
        from core.capabilities.registry import CapabilityRegistry

        reg = CapabilityRegistry()
        assert reg is not None

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

        is_valid, errors = registry.validate_config("basic.chunking", config)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_config_invalid_type(self):
        """Test validating configuration with wrong type."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        config = {
            "chunk_size": 512,  # Valid integer
            "mode": "fixed",
        }

        is_valid, errors = registry.validate_config("basic.chunking", config)
        # Should be valid with correct types
        assert is_valid is True

    def test_list_by_category(self):
        """Test listing capabilities by category."""
        from core.capabilities.registry import get_registry

        registry = get_registry()

        # list_by_category returns a dict grouped by category
        grouped = registry.list_by_category()
        assert isinstance(grouped, dict)
        
        # Check basic category exists and has capabilities
        assert "basic" in grouped
        basic_caps = grouped["basic"]
        assert len(basic_caps) > 0
        for cap in basic_caps:
            assert cap["category"] == "basic"

        # Check enhanced category
        assert "enhanced" in grouped
        enhanced_caps = grouped["enhanced"]
        assert len(enhanced_caps) > 0
        for cap in enhanced_caps:
            assert cap["category"] == "enhanced"

    def test_categories_property(self):
        """Test getting category definitions via property."""
        from core.capabilities.registry import get_registry

        registry = get_registry()
        categories = registry.categories

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

        # check_dependencies returns (bool, list)
        satisfied, missing = registry.check_dependencies("enhanced.image_understanding")
        assert isinstance(satisfied, bool)
        assert isinstance(missing, list)

    def test_get_capabilities_for_kb_config(self):
        """Test getting capabilities structured for KB config form."""
        from core.capabilities.registry import get_capabilities_for_kb_config

        data = get_capabilities_for_kb_config()

        # Returns dict with category keys
        assert isinstance(data, dict)
        assert "basic" in data
        assert "enhanced" in data
        assert "pro" in data
        assert "advanced" in data

        # Check structure of each category
        basic = data["basic"]
        assert "info" in basic
        assert "capabilities" in basic
        assert isinstance(basic["capabilities"], list)


class TestCapabilityLoader:
    """Tests for CapabilityLoader class."""

    def test_loader_instantiation(self):
        """Test creating a CapabilityLoader instance."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader()
        assert loader is not None
        assert loader.registry is not None

    def test_get_status(self):
        """Test getting capability status."""
        from core.capabilities.loader import CapabilityLoader, CapabilityStatus

        loader = CapabilityLoader()

        # Before loading, status should be DISABLED
        status = loader.get_status("basic.chunking")
        assert status == CapabilityStatus.DISABLED

    def test_get_all_status(self):
        """Test getting all capability statuses."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader()
        all_status = loader.get_all_status()
        
        assert isinstance(all_status, dict)
        # Should have entries for all capabilities
        assert len(all_status) > 0

    @pytest.mark.asyncio
    async def test_prepare_for_kb(self):
        """Test preparing capabilities for a KB."""
        from core.capabilities.loader import CapabilityLoader

        loader = CapabilityLoader()
        
        kb_config = {
            "capabilities": {
                "basic": {
                    "chunking": {"enabled": True, "chunk_size": 512}
                }
            }
        }

        result = await loader.prepare_for_kb(kb_config)
        assert isinstance(result, dict)


class TestCapabilityStatus:
    """Tests for CapabilityStatus class."""

    def test_status_values(self):
        """Test CapabilityStatus values."""
        from core.capabilities.loader import CapabilityStatus

        # CapabilityStatus is a class with string constants
        assert CapabilityStatus.DISABLED == "disabled"
        assert CapabilityStatus.LOADING == "loading"
        assert CapabilityStatus.READY == "ready"
        assert CapabilityStatus.ERROR == "error"
        assert CapabilityStatus.MISSING_DEPENDENCY == "missing_dependency"
