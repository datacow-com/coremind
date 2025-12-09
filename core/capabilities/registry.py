"""
Capability Registry - Load and manage capability definitions.

Provides programmatic access to manifest.yaml for:
- API endpoints (list capabilities, get configs)
- UI rendering (cards, forms)
- Runtime capability loading
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

MANIFEST_PATH = Path(__file__).parent / "manifest.yaml"


@lru_cache(maxsize=1)
def _load_manifest() -> dict[str, Any]:
    """Load and cache the capability manifest."""
    if not MANIFEST_PATH.exists():
        return {"capabilities": {}, "categories": {}}

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class CapabilityRegistry:
    """
    Registry for capability definitions.

    Usage:
        registry = CapabilityRegistry()

        # List all capabilities for UI
        caps = registry.list_capabilities()

        # Get single capability
        cap = registry.get("enhanced.table_recognition")

        # Get config schema for form generation
        schema = registry.get_config_schema("enhanced.table_recognition")
    """

    def __init__(self):
        self._manifest = _load_manifest()

    def reload(self) -> None:
        """Force reload manifest (useful for hot updates)."""
        _load_manifest.cache_clear()
        self._manifest = _load_manifest()

    @property
    def categories(self) -> dict[str, dict]:
        """Get category definitions."""
        return self._manifest.get("categories", {})

    @property
    def capabilities(self) -> dict[str, dict]:
        """Get all capability definitions."""
        return self._manifest.get("capabilities", {})

    def list_capabilities(
        self, category: str | None = None, include_disabled: bool = True
    ) -> list[dict[str, Any]]:
        """
        List capabilities for UI display.

        Returns list of capability summaries suitable for card rendering.
        """
        result = []

        for cap_key, cap_def in self.capabilities.items():
            cap_category = cap_def.get("category", "")

            # Filter by category if specified
            if category and cap_category != category:
                continue

            # Build summary for UI
            summary = {
                "id": cap_def.get("id", f"{cap_category}.{cap_key}"),
                "key": cap_key,
                "name": cap_def.get("name", cap_key),
                "name_en": cap_def.get("name_en", ""),
                "description": cap_def.get("description", ""),
                "description_en": cap_def.get("description_en", ""),
                "category": cap_category,
                "category_info": self.categories.get(cap_category, {}),
                "icon": cap_def.get("icon", "cube"),
                "use_case": cap_def.get("use_case", ""),
                "default_enabled": cap_def.get("default_enabled", False),
                "user_configurable": cap_def.get("user_configurable", True),
                "always_on": cap_def.get("always_on", False),
                "requires_gpu": cap_def.get("requires_gpu", False),
                "gpu_memory_mb": cap_def.get("gpu_memory_mb", 0),
                "supported_formats": cap_def.get("supported_formats", []),
                "requires": cap_def.get("requires", []),
                "has_config": cap_def.get("config_schema") is not None,
            }

            result.append(summary)

        # Sort by category order, then by name
        category_order = {k: v.get("order", 99) for k, v in self.categories.items()}
        result.sort(key=lambda x: (category_order.get(x["category"], 99), x["name"]))

        return result

    def list_by_category(self) -> dict[str, list[dict[str, Any]]]:
        """
        List capabilities grouped by category.

        Returns: {category_key: [capability_summaries]}
        """
        all_caps = self.list_capabilities()
        grouped: dict[str, list] = {}

        for cap in all_caps:
            cat = cap["category"]
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(cap)

        return grouped

    def get(self, capability_id: str) -> dict[str, Any] | None:
        """
        Get full capability definition by ID.

        Args:
            capability_id: e.g., "enhanced.table_recognition" or just "table_recognition"
        """
        # Try exact match first
        for cap_key, cap_def in self.capabilities.items():
            if cap_def.get("id") == capability_id:
                return cap_def

        # Try by key
        if capability_id in self.capabilities:
            return self.capabilities[capability_id]

        # Try without category prefix
        short_id = capability_id.split(".")[-1] if "." in capability_id else capability_id
        if short_id in self.capabilities:
            return self.capabilities[short_id]

        return None

    def get_config_schema(self, capability_id: str) -> dict[str, Any] | None:
        """
        Get config schema for a capability.

        Returns JSON Schema-like structure for UI form generation.
        """
        cap = self.get(capability_id)
        if not cap:
            return None

        return cap.get("config_schema")

    def get_default_config(self, capability_id: str) -> dict[str, Any]:
        """
        Get default configuration values for a capability.
        """
        schema = self.get_config_schema(capability_id)
        if not schema or schema.get("type") != "object":
            return {}

        defaults = {}
        properties = schema.get("properties", {})

        for prop_key, prop_def in properties.items():
            if "default" in prop_def:
                defaults[prop_key] = prop_def["default"]

        return defaults

    def get_implementation(self, capability_id: str) -> dict[str, str] | None:
        """
        Get implementation info for loading the capability module.

        Returns: {"module": "...", "class": "..." or "function": "..."}
        """
        cap = self.get(capability_id)
        if not cap:
            return None

        return cap.get("implementation")

    def validate_config(self, capability_id: str, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate a capability configuration.

        Returns: (is_valid, error_messages)
        """
        schema = self.get_config_schema(capability_id)
        if not schema:
            return True, []

        errors = []
        properties = schema.get("properties", {})

        for prop_key, prop_def in properties.items():
            value = config.get(prop_key)

            # Check required (no default means required)
            if value is None and "default" not in prop_def:
                errors.append(f"Missing required field: {prop_key}")
                continue

            if value is None:
                continue

            # Type check
            expected_type = prop_def.get("type")
            if expected_type == "integer" and not isinstance(value, int):
                errors.append(f"{prop_key} must be an integer")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{prop_key} must be a number")
            elif expected_type == "string" and not isinstance(value, str):
                errors.append(f"{prop_key} must be a string")
            elif expected_type == "boolean" and not isinstance(value, bool):
                errors.append(f"{prop_key} must be a boolean")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"{prop_key} must be an array")

            # Range check
            if expected_type in ("integer", "number"):
                if "minimum" in prop_def and value < prop_def["minimum"]:
                    errors.append(f"{prop_key} must be >= {prop_def['minimum']}")
                if "maximum" in prop_def and value > prop_def["maximum"]:
                    errors.append(f"{prop_key} must be <= {prop_def['maximum']}")

            # Enum check
            if "enum" in prop_def and value not in prop_def["enum"]:
                errors.append(f"{prop_key} must be one of: {prop_def['enum']}")

        return len(errors) == 0, errors

    def check_dependencies(self, capability_id: str) -> tuple[bool, list[str]]:
        """
        Check if a capability's dependencies are satisfied.

        Returns: (all_satisfied, missing_dependencies)
        """
        cap = self.get(capability_id)
        if not cap:
            return False, [f"Unknown capability: {capability_id}"]

        requires = cap.get("requires", [])
        if not requires:
            return True, []

        missing = []
        dependencies = self._manifest.get("dependencies", {})

        for req in requires:
            dep_def = dependencies.get(req, {})

            # Check environment variables
            env_vars = dep_def.get("check_env", [])
            if env_vars and not any(os.environ.get(v) for v in env_vars):
                missing.append(f"{req}: Set one of {env_vars}")

            # Check if required capability is available
            cap_id = dep_def.get("capability_id")
            if cap_id and not self.get(cap_id):
                missing.append(f"{req}: Capability {cap_id} not found")

        return len(missing) == 0, missing


# Convenience functions
def get_registry() -> CapabilityRegistry:
    """Get singleton registry instance."""
    return CapabilityRegistry()


def list_all_capabilities() -> list[dict[str, Any]]:
    """List all capabilities for API response."""
    return get_registry().list_capabilities()


def get_capability(capability_id: str) -> dict[str, Any] | None:
    """Get a single capability by ID."""
    return get_registry().get(capability_id)


def get_capabilities_for_kb_config() -> dict[str, Any]:
    """
    Get capabilities structured for KB configuration form.

    Returns nested structure: {category: [capabilities]}
    """
    registry = get_registry()
    by_category = registry.list_by_category()

    result = {}
    for cat_key in ["basic", "enhanced", "pro", "advanced"]:
        cat_info = registry.categories.get(cat_key, {})
        result[cat_key] = {
            "info": cat_info,
            "capabilities": by_category.get(cat_key, []),
        }

    return result
