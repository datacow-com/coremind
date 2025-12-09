"""
Capability Framework - Making core capabilities visible, configurable, and usable.

设计原则:
- 不沉默: 每个能力在 UI 中可见
- 可选择: KB 级别启用/禁用
- 可配置: 每个能力有可调参数
- 可使用: 配置后立即生效

Usage:
    from core.capabilities import get_registry, list_all_capabilities

    # List all capabilities for UI
    caps = list_all_capabilities()

    # Get structured data for KB config form
    from core.capabilities import get_capabilities_for_kb_config
    form_data = get_capabilities_for_kb_config()

    # Load capabilities for a KB
    from core.capabilities import prepare_kb_capabilities
    status = await prepare_kb_capabilities("my_kb", kb_config)
"""

from core.capabilities.loader import (
    CapabilityLoader,
    CapabilityStatus,
    get_loader_for_kb,
    prepare_kb_capabilities,
)
from core.capabilities.registry import (
    CapabilityRegistry,
    get_capabilities_for_kb_config,
    get_capability,
    get_registry,
    list_all_capabilities,
)

__all__ = [
    # Registry
    "CapabilityRegistry",
    "get_registry",
    "list_all_capabilities",
    "get_capability",
    "get_capabilities_for_kb_config",
    # Loader
    "CapabilityLoader",
    "CapabilityStatus",
    "get_loader_for_kb",
    "prepare_kb_capabilities",
]
