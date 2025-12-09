"""
Capability Loader - Dynamically load and manage capability instances.

按 KB 配置动态加载能力模块，支持：
- 懒加载（只加载启用的能力）
- 状态跟踪（ready/loading/error/disabled）
- 热更新（配置变更无需重启）
"""

import asyncio
import importlib
import logging
from typing import Any

from core.capabilities.registry import get_registry

logger = logging.getLogger(__name__)


class CapabilityStatus:
    """Capability status constants."""

    DISABLED = "disabled"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    MISSING_DEPENDENCY = "missing_dependency"


class CapabilityLoader:
    """
    Dynamic capability loader for knowledge bases.

    Usage:
        loader = CapabilityLoader()

        # Prepare capabilities for a KB
        status = await loader.prepare_for_kb(kb_config)

        # Get a loaded capability instance
        table_extractor = loader.get("enhanced.table_recognition")

        # Check all status
        all_status = loader.get_all_status()
    """

    def __init__(self):
        self.registry = get_registry()
        self._instances: dict[str, Any] = {}
        self._status: dict[str, str] = {}
        self._errors: dict[str, str] = {}
        self._configs: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def prepare_for_kb(
        self, kb_config: dict[str, Any], force_reload: bool = False
    ) -> dict[str, str]:
        """
        Prepare capabilities for a KB based on its configuration.

        Args:
            kb_config: KB configuration with 'capabilities' field
            force_reload: Force reload even if already loaded

        Returns:
            Dict mapping capability_id to status
        """
        async with self._lock:
            capabilities_config = kb_config.get("capabilities", {})
            result = {}

            # Process each category
            for category in ["basic", "enhanced", "pro", "advanced"]:
                cat_config = capabilities_config.get(category, {})

                for cap_key, cap_config in cat_config.items():
                    cap_id = f"{category}.{cap_key}"

                    # Determine if enabled
                    if isinstance(cap_config, bool):
                        enabled = cap_config
                        config = {}
                    elif isinstance(cap_config, dict):
                        enabled = cap_config.get("enabled", True)
                        config = {k: v for k, v in cap_config.items() if k != "enabled"}
                    else:
                        enabled = False
                        config = {}

                    if enabled:
                        status = await self._load_capability(cap_id, config, force_reload)
                    else:
                        status = CapabilityStatus.DISABLED
                        self._status[cap_id] = status

                    result[cap_id] = status

            # Always load basic capabilities
            for cap in self.registry.list_capabilities(category="basic"):
                cap_id = cap["id"]
                if cap_id not in result or cap.get("always_on"):
                    default_config = self.registry.get_default_config(cap_id)
                    status = await self._load_capability(cap_id, default_config, force_reload)
                    result[cap_id] = status

            return result

    async def _load_capability(
        self, cap_id: str, config: dict[str, Any], force_reload: bool = False
    ) -> str:
        """Load a single capability."""
        # Skip if already loaded and not forcing reload
        if not force_reload and cap_id in self._instances:
            return self._status.get(cap_id, CapabilityStatus.READY)

        self._status[cap_id] = CapabilityStatus.LOADING

        try:
            # Get capability definition
            cap_def = self.registry.get(cap_id)
            if not cap_def:
                raise ValueError(f"Unknown capability: {cap_id}")

            # Check dependencies
            ok, missing = self.registry.check_dependencies(cap_id)
            if not ok:
                self._status[cap_id] = CapabilityStatus.MISSING_DEPENDENCY
                self._errors[cap_id] = f"Missing: {', '.join(missing)}"
                logger.warning(f"Capability {cap_id} missing dependencies: {missing}")
                return CapabilityStatus.MISSING_DEPENDENCY

            # Validate config
            merged_config = self.registry.get_default_config(cap_id)
            merged_config.update(config)

            ok, errors = self.registry.validate_config(cap_id, merged_config)
            if not ok:
                self._status[cap_id] = CapabilityStatus.ERROR
                self._errors[cap_id] = "; ".join(errors)
                logger.error(f"Capability {cap_id} config invalid: {errors}")
                return CapabilityStatus.ERROR

            # Load implementation
            impl = cap_def.get("implementation")
            if not impl:
                # No implementation needed (e.g., just config)
                self._instances[cap_id] = None
                self._configs[cap_id] = merged_config
                self._status[cap_id] = CapabilityStatus.READY
                return CapabilityStatus.READY

            instance = await self._import_and_create(impl, merged_config)

            self._instances[cap_id] = instance
            self._configs[cap_id] = merged_config
            self._status[cap_id] = CapabilityStatus.READY

            logger.info(f"Capability {cap_id} loaded successfully")
            return CapabilityStatus.READY

        except Exception as e:
            self._status[cap_id] = CapabilityStatus.ERROR
            self._errors[cap_id] = str(e)
            logger.exception(f"Failed to load capability {cap_id}")
            return CapabilityStatus.ERROR

    async def _import_and_create(self, impl: dict[str, str], config: dict[str, Any]) -> Any:
        """Import module and create instance."""
        module_path = impl.get("module")
        class_name = impl.get("class")
        func_name = impl.get("function")

        if not module_path:
            raise ValueError("Implementation missing 'module'")

        # Import module
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            raise ImportError(f"Cannot import {module_path}: {e}")

        # Get class or function
        if class_name:
            cls = getattr(module, class_name, None)
            if cls is None:
                raise AttributeError(f"{module_path} has no class {class_name}")

            # Create instance
            # Try with config, fallback to no args
            try:
                instance = cls(config=config)
            except TypeError:
                try:
                    instance = cls(**config)
                except TypeError:
                    instance = cls()

            return instance

        elif func_name:
            func = getattr(module, func_name, None)
            if func is None:
                raise AttributeError(f"{module_path} has no function {func_name}")

            # Return the function itself or call it with config
            if config:
                try:
                    return func(**config)
                except TypeError:
                    return func
            return func

        else:
            raise ValueError("Implementation must specify 'class' or 'function'")

    def get(self, cap_id: str) -> Any:
        """
        Get a loaded capability instance.

        Raises:
            RuntimeError: If capability not loaded or in error state
        """
        status = self._status.get(cap_id)

        if status == CapabilityStatus.DISABLED:
            raise RuntimeError(f"Capability {cap_id} is disabled")
        elif status == CapabilityStatus.ERROR:
            error = self._errors.get(cap_id, "Unknown error")
            raise RuntimeError(f"Capability {cap_id} failed to load: {error}")
        elif status == CapabilityStatus.MISSING_DEPENDENCY:
            error = self._errors.get(cap_id, "Missing dependencies")
            raise RuntimeError(f"Capability {cap_id} missing dependencies: {error}")
        elif status == CapabilityStatus.LOADING:
            raise RuntimeError(f"Capability {cap_id} is still loading")
        elif status != CapabilityStatus.READY:
            raise RuntimeError(f"Capability {cap_id} not loaded")

        return self._instances.get(cap_id)

    def get_config(self, cap_id: str) -> dict[str, Any]:
        """Get the configuration used for a capability."""
        return self._configs.get(cap_id, {})

    def get_status(self, cap_id: str) -> str:
        """Get status of a single capability."""
        return self._status.get(cap_id, CapabilityStatus.DISABLED)

    def get_error(self, cap_id: str) -> str | None:
        """Get error message if capability failed."""
        return self._errors.get(cap_id)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all capabilities.

        Returns structured status for UI display.
        """
        result = {}

        for cap in self.registry.list_capabilities():
            cap_id = cap["id"]
            status = self._status.get(cap_id, CapabilityStatus.DISABLED)

            result[cap_id] = {
                "id": cap_id,
                "name": cap["name"],
                "category": cap["category"],
                "status": status,
                "error": self._errors.get(cap_id) if status == CapabilityStatus.ERROR else None,
                "config": self._configs.get(cap_id, {}),
            }

        return result

    def is_ready(self, cap_id: str) -> bool:
        """Check if a capability is ready to use."""
        return self._status.get(cap_id) == CapabilityStatus.READY

    async def reload_capability(self, cap_id: str, config: dict[str, Any]) -> str:
        """Reload a single capability with new config."""
        async with self._lock:
            # Clear existing
            self._instances.pop(cap_id, None)
            self._status.pop(cap_id, None)
            self._errors.pop(cap_id, None)
            self._configs.pop(cap_id, None)

            return await self._load_capability(cap_id, config, force_reload=True)

    def unload_all(self) -> None:
        """Unload all capabilities."""
        self._instances.clear()
        self._status.clear()
        self._errors.clear()
        self._configs.clear()


# Global loader instance per KB
_kb_loaders: dict[str, CapabilityLoader] = {}


def get_loader_for_kb(kb_name: str) -> CapabilityLoader:
    """Get or create a capability loader for a KB."""
    if kb_name not in _kb_loaders:
        _kb_loaders[kb_name] = CapabilityLoader()
    return _kb_loaders[kb_name]


async def prepare_kb_capabilities(kb_name: str, kb_config: dict[str, Any]) -> dict[str, str]:
    """Prepare capabilities for a KB."""
    loader = get_loader_for_kb(kb_name)
    return await loader.prepare_for_kb(kb_config)
