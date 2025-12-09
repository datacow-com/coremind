"""
Capability API Routes - Expose capabilities to frontend.

提供能力清单、配置、状态等 API 接口，供 UI 展示和配置。
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.capabilities import (
    get_capabilities_for_kb_config,
    get_registry,
)
from core.capabilities.loader import (
    CapabilityStatus,
    get_loader_for_kb,
    prepare_kb_capabilities,
)

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


# ═══════════════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class CapabilitySummary(BaseModel):
    """Capability summary for list view."""

    id: str
    name: str
    name_en: str
    description: str
    category: str
    icon: str
    use_case: str
    default_enabled: bool
    requires_gpu: bool
    has_config: bool


class CapabilityDetail(BaseModel):
    """Full capability detail."""

    id: str
    name: str
    name_en: str
    description: str
    description_en: str
    category: str
    icon: str
    use_case: str
    default_enabled: bool
    user_configurable: bool
    requires_gpu: bool
    gpu_memory_mb: int
    supported_formats: list[str]
    requires: list[str]
    config_schema: dict | None
    implementation: dict | None


class CapabilityStatusResponse(BaseModel):
    """Capability status for a KB."""

    id: str
    name: str
    category: str
    status: str
    error: str | None
    config: dict


class UpdateConfigRequest(BaseModel):
    """Request to update capability config."""

    capability_id: str
    config: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/list", response_model=list[CapabilitySummary])
async def list_capabilities(category: str | None = None):
    """
    列出所有能力

    - **category**: 可选，按分类过滤 (basic/enhanced/pro/advanced)

    用于 UI 能力卡片列表展示。
    """
    registry = get_registry()
    caps = registry.list_capabilities(category=category)

    return [
        CapabilitySummary(
            id=c["id"],
            name=c["name"],
            name_en=c["name_en"],
            description=c["description"],
            category=c["category"],
            icon=c["icon"],
            use_case=c["use_case"],
            default_enabled=c["default_enabled"],
            requires_gpu=c["requires_gpu"],
            has_config=c["has_config"],
        )
        for c in caps
    ]


@router.get("/categories")
async def get_categories():
    """
    获取能力分类信息

    用于 UI 分类标签/Tab 展示。
    """
    registry = get_registry()
    return registry.categories


@router.get("/grouped")
async def get_grouped_capabilities():
    """
    获取按分类分组的能力列表

    用于 KB 配置表单渲染。
    """
    return get_capabilities_for_kb_config()


@router.get("/detail/{capability_id}")
async def get_capability_detail(capability_id: str):
    """
    获取单个能力的详细信息

    包含完整配置 schema，用于配置表单生成。
    """
    registry = get_registry()
    cap = registry.get(capability_id)

    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    return CapabilityDetail(
        id=cap.get("id", capability_id),
        name=cap.get("name", ""),
        name_en=cap.get("name_en", ""),
        description=cap.get("description", ""),
        description_en=cap.get("description_en", ""),
        category=cap.get("category", ""),
        icon=cap.get("icon", "cube"),
        use_case=cap.get("use_case", ""),
        default_enabled=cap.get("default_enabled", False),
        user_configurable=cap.get("user_configurable", True),
        requires_gpu=cap.get("requires_gpu", False),
        gpu_memory_mb=cap.get("gpu_memory_mb", 0),
        supported_formats=cap.get("supported_formats", []),
        requires=cap.get("requires", []),
        config_schema=cap.get("config_schema"),
        implementation=cap.get("implementation"),
    )


@router.get("/config-schema/{capability_id}")
async def get_capability_config_schema(capability_id: str):
    """
    获取能力配置 Schema

    返回 JSON Schema 格式，用于动态表单生成。
    """
    registry = get_registry()
    schema = registry.get_config_schema(capability_id)

    if schema is None:
        # Capability exists but has no configurable options
        cap = registry.get(capability_id)
        if cap:
            return {"type": "object", "properties": {}, "message": "No configurable options"}
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    return schema


@router.get("/default-config/{capability_id}")
async def get_default_capability_config(capability_id: str):
    """
    获取能力默认配置

    用于配置表单初始值。
    """
    registry = get_registry()
    cap = registry.get(capability_id)

    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    return registry.get_default_config(capability_id)


@router.post("/validate-config/{capability_id}")
async def validate_capability_config(capability_id: str, config: dict[str, Any]):
    """
    验证能力配置

    在保存前检查配置是否有效。
    """
    registry = get_registry()
    cap = registry.get(capability_id)

    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    is_valid, errors = registry.validate_config(capability_id, config)

    return {
        "valid": is_valid,
        "errors": errors,
    }


@router.get("/status/{kb_name}")
async def get_kb_capability_status(kb_name: str):
    """
    获取 KB 的能力状态

    返回该 KB 所有能力的加载状态。
    """
    loader = get_loader_for_kb(kb_name)
    return loader.get_all_status()


@router.post("/prepare/{kb_name}")
async def prepare_kb_caps(kb_name: str, kb_config: dict[str, Any]):
    """
    为 KB 准备能力

    根据 KB 配置加载所需的能力模块。
    """
    try:
        status = await prepare_kb_capabilities(kb_name, kb_config)

        # Count by status
        ready_count = sum(1 for s in status.values() if s == CapabilityStatus.READY)
        error_count = sum(1 for s in status.values() if s == CapabilityStatus.ERROR)
        disabled_count = sum(1 for s in status.values() if s == CapabilityStatus.DISABLED)

        return {
            "success": error_count == 0,
            "summary": {
                "ready": ready_count,
                "error": error_count,
                "disabled": disabled_count,
                "total": len(status),
            },
            "details": status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload/{kb_name}/{capability_id}")
async def reload_kb_capability(kb_name: str, capability_id: str, config: dict[str, Any]):
    """
    重新加载单个能力

    用于配置变更后的热更新。
    """
    loader = get_loader_for_kb(kb_name)

    try:
        status = await loader.reload_capability(capability_id, config)

        return {
            "capability_id": capability_id,
            "status": status,
            "error": loader.get_error(capability_id) if status == CapabilityStatus.ERROR else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dependencies/{capability_id}")
async def check_capability_dependencies(capability_id: str):
    """
    检查能力依赖

    返回依赖是否满足。
    """
    registry = get_registry()
    cap = registry.get(capability_id)

    if not cap:
        raise HTTPException(status_code=404, detail=f"Capability not found: {capability_id}")

    ok, missing = registry.check_dependencies(capability_id)

    return {
        "satisfied": ok,
        "missing": missing,
        "requires": cap.get("requires", []),
    }
