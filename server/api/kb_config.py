"""
KB Config API - KB 能力配置 API

提供 KB 级别的能力配置管理接口：
- GET /api/kb/{kb_name}/capabilities - 获取 KB 启用的能力列表
- PUT /api/kb/{kb_name}/capabilities - 更新 KB 能力配置
- GET /api/kb/{kb_name}/strategy - 获取合并后的完整策略
- GET /api/kb/{kb_name}/capabilities/history - 获取配置版本历史
- GET /api/kb/{kb_name}/capabilities/export - 导出配置
- POST /api/kb/{kb_name}/capabilities/import - 导入配置

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 12.1, 12.2, 12.3, 12.4, 12.5, 13.1, 13.2
"""

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.capabilities import get_registry
from core.pipeline.kb_merge import merge_kb_params
from core.storage.kb_config import default_kb_config, load_kb_config, save_kb_config
from server.api.config_storage import (
    CapabilityConfig,
    ConfigExport,
    ConfigVersionEntry,
    get_config_storage,
)

router = APIRouter(prefix="/kb", tags=["kb-config"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════════


class CapabilitySettings(BaseModel):
    """Single capability settings."""

    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class KBCapabilityConfig(BaseModel):
    """KB capability configuration request/response."""

    capabilities: dict[str, CapabilitySettings] = Field(default_factory=dict)


class ValidationError(BaseModel):
    """Validation error detail."""

    capability_id: str
    field: str
    message: str


class KBCapabilityResponse(BaseModel):
    """Response for GET /api/kb/{kb_name}/capabilities."""

    kb_name: str
    capabilities: dict[str, CapabilitySettings]
    updated_at: str | None = None


class KBCapabilityUpdateResponse(BaseModel):
    """Response for PUT /api/kb/{kb_name}/capabilities."""

    kb_name: str
    capabilities: dict[str, CapabilitySettings]
    updated_at: str
    validation_errors: list[ValidationError] = Field(default_factory=list)


class IngestStrategyConfig(BaseModel):
    """Ingest strategy configuration."""

    chunking_mode: str = "fixed"
    chunk_size: int = 512
    chunk_overlap: int = 50
    ocr_enabled: bool = False
    ocr_engine: str = "paddleocr"
    table_extraction: bool = False
    image_understanding: bool = False


class RetrievalStrategyConfig(BaseModel):
    """Retrieval strategy configuration."""

    top_k: int = 5
    candidate_k: int = 50
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    reranker_enabled: bool = True
    reranker_threshold: float = 0.2


class MergedStrategy(BaseModel):
    """Merged complete strategy configuration."""

    kb_name: str
    ingest: IngestStrategyConfig
    retrieval: RetrievalStrategyConfig
    capabilities: dict[str, CapabilitySettings]
    raw_config: dict[str, Any] = Field(default_factory=dict)


class ConfigChangeEvent(BaseModel):
    """Configuration change event model."""

    event_type: str = "config_change"
    kb_name: str
    timestamp: str
    changed_capabilities: list[str]
    previous_config: dict[str, Any] | None = None
    new_config: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# Event Emission (Requirements 1.5)
# ═══════════════════════════════════════════════════════════════════════════════

# Event subscribers - can be extended for different consumers
_config_change_subscribers: list[Any] = []


def subscribe_to_config_changes(callback: Any) -> None:
    """Subscribe to configuration change events."""
    _config_change_subscribers.append(callback)


def unsubscribe_from_config_changes(callback: Any) -> None:
    """Unsubscribe from configuration change events."""
    if callback in _config_change_subscribers:
        _config_change_subscribers.remove(callback)


async def emit_config_change_event(event: ConfigChangeEvent) -> None:
    """Emit configuration change event to all subscribers."""
    for subscriber in _config_change_subscribers:
        try:
            if asyncio.iscoroutinefunction(subscriber):
                await subscriber(event)
            else:
                subscriber(event)
        except Exception:
            # Don't let subscriber errors affect the main flow
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Validation (Requirements 1.4)
# ═══════════════════════════════════════════════════════════════════════════════


def validate_capability_config(
    capability_id: str, config: dict[str, Any]
) -> tuple[bool, list[ValidationError]]:
    """
    Validate capability configuration against its schema.

    Returns: (is_valid, validation_errors)
    """
    registry = get_registry()
    errors: list[ValidationError] = []

    # Get capability definition
    cap = registry.get(capability_id)
    if not cap:
        errors.append(
            ValidationError(
                capability_id=capability_id,
                field="",
                message=f"Unknown capability: {capability_id}",
            )
        )
        return False, errors

    # Get config schema
    schema = cap.get("config_schema")
    if not schema:
        # No schema means no validation needed
        return True, []

    properties = schema.get("properties", {})

    for prop_key, prop_def in properties.items():
        value = config.get(prop_key)

        # Check required fields (no default means required)
        if value is None and "default" not in prop_def:
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"Missing required field: {prop_key}",
                )
            )
            continue

        if value is None:
            continue

        # Type validation
        expected_type = prop_def.get("type")
        if expected_type == "integer" and not isinstance(value, int):
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be an integer",
                )
            )
        elif expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be a number",
                )
            )
        elif expected_type == "string" and not isinstance(value, str):
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be a string",
                )
            )
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be a boolean",
                )
            )
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be an array",
                )
            )

        # Range validation
        if expected_type in ("integer", "number") and isinstance(value, (int, float)):
            if "minimum" in prop_def and value < prop_def["minimum"]:
                errors.append(
                    ValidationError(
                        capability_id=capability_id,
                        field=prop_key,
                        message=f"{prop_key} must be >= {prop_def['minimum']}",
                    )
                )
            if "maximum" in prop_def and value > prop_def["maximum"]:
                errors.append(
                    ValidationError(
                        capability_id=capability_id,
                        field=prop_key,
                        message=f"{prop_key} must be <= {prop_def['maximum']}",
                    )
                )

        # Enum validation
        if "enum" in prop_def and value not in prop_def["enum"]:
            errors.append(
                ValidationError(
                    capability_id=capability_id,
                    field=prop_key,
                    message=f"{prop_key} must be one of: {prop_def['enum']}",
                )
            )

    return len(errors) == 0, errors


def validate_all_capabilities(
    capabilities: dict[str, CapabilitySettings],
) -> tuple[bool, list[ValidationError]]:
    """Validate all capability configurations."""
    all_errors: list[ValidationError] = []

    for cap_id, settings in capabilities.items():
        if settings.enabled:
            _, errors = validate_capability_config(cap_id, settings.config)
            all_errors.extend(errors)

    return len(all_errors) == 0, all_errors


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def extract_capabilities_from_kb_config(kb_config: dict[str, Any]) -> dict[str, CapabilitySettings]:
    """Extract capability settings from KB config structure."""
    result: dict[str, CapabilitySettings] = {}
    capabilities = kb_config.get("capabilities", {})

    for category, category_caps in capabilities.items():
        if not isinstance(category_caps, dict):
            continue

        for cap_key, cap_value in category_caps.items():
            # Build full capability ID
            cap_id = f"{category}.{cap_key}"

            if isinstance(cap_value, bool):
                # Simple enabled/disabled
                result[cap_id] = CapabilitySettings(enabled=cap_value, config={})
            elif isinstance(cap_value, dict):
                # Full config with enabled flag
                enabled = cap_value.get("enabled", True)
                config = {k: v for k, v in cap_value.items() if k != "enabled"}
                result[cap_id] = CapabilitySettings(enabled=enabled, config=config)

    return result


def merge_capabilities_to_kb_config(
    kb_config: dict[str, Any], capabilities: dict[str, CapabilitySettings]
) -> dict[str, Any]:
    """Merge capability settings back into KB config structure."""
    # Ensure capabilities dict exists
    if "capabilities" not in kb_config:
        kb_config["capabilities"] = {}

    for cap_id, settings in capabilities.items():
        # Parse category from capability ID
        parts = cap_id.split(".")
        if len(parts) >= 2:
            category = parts[0]
            cap_key = ".".join(parts[1:])
        else:
            # Try to find category from registry
            registry = get_registry()
            cap = registry.get(cap_id)
            if cap:
                category = cap.get("category", "basic")
                cap_key = cap_id
            else:
                category = "basic"
                cap_key = cap_id

        # Ensure category exists
        if category not in kb_config["capabilities"]:
            kb_config["capabilities"][category] = {}

        # Build config value
        if settings.config:
            config_value = {"enabled": settings.enabled, **settings.config}
        else:
            config_value = {"enabled": settings.enabled}

        kb_config["capabilities"][category][cap_key] = config_value

    return kb_config


# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{kb_name}/capabilities", response_model=KBCapabilityResponse)
async def get_kb_capabilities(kb_name: str) -> KBCapabilityResponse:
    """
    获取 KB 启用的能力列表及其配置

    Requirements: 1.1
    """
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e

    capabilities = extract_capabilities_from_kb_config(kb_config)

    return KBCapabilityResponse(
        kb_name=kb_name,
        capabilities=capabilities,
        updated_at=kb_config.get("updated_at"),
    )


@router.put("/{kb_name}/capabilities", response_model=KBCapabilityUpdateResponse)
async def update_kb_capabilities(
    kb_name: str, request: KBCapabilityConfig
) -> KBCapabilityUpdateResponse:
    """
    更新 KB 能力配置

    Requirements: 1.2, 1.4, 1.5
    """
    # Load existing config
    try:
        kb_config = load_kb_config(kb_name)
    except Exception:
        # Create new KB config if not exists
        kb_config = default_kb_config(kb_name)

    # Store previous config for event
    previous_capabilities = extract_capabilities_from_kb_config(kb_config)

    # Validate all capability configurations
    is_valid, validation_errors = validate_all_capabilities(request.capabilities)

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid capability configuration",
                "errors": [e.model_dump() for e in validation_errors],
            },
        )

    # Merge new capabilities into KB config
    kb_config = merge_capabilities_to_kb_config(kb_config, request.capabilities)

    # Update timestamp
    updated_at = datetime.utcnow().isoformat() + "Z"
    kb_config["updated_at"] = updated_at

    # Save config
    try:
        save_kb_config(kb_name, kb_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}") from e

    # Emit config change event (Requirements 1.5)
    changed_capabilities = [
        cap_id
        for cap_id in request.capabilities
        if cap_id not in previous_capabilities
        or previous_capabilities[cap_id] != request.capabilities[cap_id]
    ]

    if changed_capabilities:
        event = ConfigChangeEvent(
            kb_name=kb_name,
            timestamp=updated_at,
            changed_capabilities=changed_capabilities,
            previous_config={k: v.model_dump() for k, v in previous_capabilities.items()},
            new_config={k: v.model_dump() for k, v in request.capabilities.items()},
        )
        await emit_config_change_event(event)

    return KBCapabilityUpdateResponse(
        kb_name=kb_name,
        capabilities=request.capabilities,
        updated_at=updated_at,
        validation_errors=[],
    )


@router.get("/{kb_name}/strategy", response_model=MergedStrategy)
async def get_kb_strategy(kb_name: str) -> MergedStrategy:
    """
    获取合并后的完整策略配置

    Requirements: 1.3
    """
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e

    # Get merged params using existing merge logic
    merged = merge_kb_params({"kb_name": kb_name})

    # Extract capabilities
    capabilities = extract_capabilities_from_kb_config(kb_config)

    # Build ingest strategy from capabilities
    chunking_config = kb_config.get("capabilities", {}).get("basic", {}).get("chunking", {})
    ocr_config = kb_config.get("capabilities", {}).get("enhanced", {}).get("ocr", {})
    table_config = kb_config.get("capabilities", {}).get("enhanced", {}).get("table_recognition", {})
    image_config = kb_config.get("capabilities", {}).get("enhanced", {}).get("image_understanding", {})

    ingest = IngestStrategyConfig(
        chunking_mode=chunking_config.get("mode", "fixed") if isinstance(chunking_config, dict) else "fixed",
        chunk_size=chunking_config.get("chunk_size", 512) if isinstance(chunking_config, dict) else 512,
        chunk_overlap=chunking_config.get("overlap", 50) if isinstance(chunking_config, dict) else 50,
        ocr_enabled=ocr_config.get("enabled", False) if isinstance(ocr_config, dict) else False,
        ocr_engine=ocr_config.get("engine", "paddleocr") if isinstance(ocr_config, dict) else "paddleocr",
        table_extraction=table_config.get("enabled", False) if isinstance(table_config, dict) else False,
        image_understanding=image_config.get("enabled", False) if isinstance(image_config, dict) else False,
    )

    # Build retrieval strategy
    reranking_config = kb_config.get("capabilities", {}).get("enhanced", {}).get("reranking", {})

    retrieval = RetrievalStrategyConfig(
        top_k=merged.get("top_k", 5),
        candidate_k=merged.get("candidate_k", 50),
        vector_weight=merged.get("vector_weight", 0.6),
        keyword_weight=merged.get("keyword_weight", 0.4),
        reranker_enabled=reranking_config.get("enabled", True) if isinstance(reranking_config, dict) else True,
        reranker_threshold=reranking_config.get("threshold", 0.2) if isinstance(reranking_config, dict) else 0.2,
    )

    return MergedStrategy(
        kb_name=kb_name,
        ingest=ingest,
        retrieval=retrieval,
        capabilities=capabilities,
        raw_config=kb_config,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Version History and Export Endpoints (Requirements 12.3, 12.4, 12.5, 13.1, 13.2)
# ═══════════════════════════════════════════════════════════════════════════════


class ConfigHistoryResponse(BaseModel):
    """Response for GET /api/kb/{kb_name}/capabilities/history."""

    kb_name: str
    history: list[ConfigVersionEntry]
    total_versions: int


class ConfigExportResponse(BaseModel):
    """Response for GET /api/kb/{kb_name}/capabilities/export."""

    kb_name: str
    version: int
    capabilities: dict[str, CapabilitySettings]
    exported_at: str
    schema_version: str = "1.0"


class ConfigImportRequest(BaseModel):
    """Request for POST /api/kb/{kb_name}/capabilities/import."""

    config: ConfigExport
    merge_strategy: str = "replace"  # replace, merge, merge_keep


class ConfigImportResponse(BaseModel):
    """Response for POST /api/kb/{kb_name}/capabilities/import."""

    kb_name: str
    version: int
    capabilities: dict[str, CapabilitySettings]
    imported_at: str


@router.get("/{kb_name}/capabilities/history", response_model=ConfigHistoryResponse)
async def get_kb_capabilities_history(
    kb_name: str,
    limit: int = Query(default=10, ge=1, le=100),
) -> ConfigHistoryResponse:
    """
    获取 KB 能力配置的版本历史

    Requirements: 12.3
    """
    storage = get_config_storage()
    history = storage.get_version_history(kb_name, limit=limit)

    return ConfigHistoryResponse(
        kb_name=kb_name,
        history=history,
        total_versions=len(history),
    )


@router.get("/{kb_name}/capabilities/version/{version}")
async def get_kb_capabilities_at_version(
    kb_name: str,
    version: int,
) -> KBCapabilityResponse:
    """
    获取 KB 能力配置的特定版本

    Requirements: 12.3, 12.4
    """
    storage = get_config_storage()
    config = storage.get_config_at_version(kb_name, version)

    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Configuration version {version} not found for KB: {kb_name}",
        )

    # Convert to CapabilitySettings format
    capabilities = {
        k: CapabilitySettings(enabled=v.enabled, config=v.config)
        for k, v in config.capabilities.items()
    }

    return KBCapabilityResponse(
        kb_name=kb_name,
        capabilities=capabilities,
        updated_at=config.updated_at.isoformat() + "Z" if config.updated_at else None,
    )


@router.get("/{kb_name}/capabilities/export", response_model=ConfigExportResponse)
async def export_kb_capabilities(kb_name: str) -> ConfigExportResponse:
    """
    导出 KB 能力配置

    Requirements: 12.4, 12.5, 13.1
    """
    storage = get_config_storage()
    export = storage.export_config(kb_name)

    if export is None:
        # Try to export from legacy config
        try:
            kb_config = load_kb_config(kb_name)
            capabilities = extract_capabilities_from_kb_config(kb_config)

            return ConfigExportResponse(
                kb_name=kb_name,
                version=1,
                capabilities=capabilities,
                exported_at=datetime.utcnow().isoformat() + "Z",
                schema_version="1.0",
            )
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"KB not found: {kb_name}",
            ) from e

    # Convert CapabilityConfig to CapabilitySettings
    capabilities = {
        k: CapabilitySettings(enabled=v.enabled, config=v.config)
        for k, v in export.capabilities.items()
    }

    return ConfigExportResponse(
        kb_name=kb_name,
        version=export.version,
        capabilities=capabilities,
        exported_at=export.exported_at,
        schema_version=export.schema_version,
    )


@router.post("/{kb_name}/capabilities/import", response_model=ConfigImportResponse)
async def import_kb_capabilities(
    kb_name: str,
    request: ConfigImportRequest,
) -> ConfigImportResponse:
    """
    导入 KB 能力配置

    Requirements: 13.2, 13.3
    """
    # Validate merge strategy
    valid_strategies = ["replace", "merge", "merge_keep"]
    if request.merge_strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid merge strategy. Must be one of: {valid_strategies}",
        )

    # Validate imported config
    is_valid, validation_errors = validate_all_capabilities(
        {k: CapabilitySettings(enabled=v.enabled, config=v.config) 
         for k, v in request.config.capabilities.items()}
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid capability configuration in import",
                "errors": [e.model_dump() for e in validation_errors],
            },
        )

    storage = get_config_storage()
    result = storage.import_config(
        kb_name=kb_name,
        config_export=request.config,
        merge_strategy=request.merge_strategy,
    )

    # Convert to CapabilitySettings format
    capabilities = {
        k: CapabilitySettings(enabled=v.enabled, config=v.config)
        for k, v in result.capabilities.items()
    }

    imported_at = datetime.utcnow().isoformat() + "Z"

    # Emit config change event
    event = ConfigChangeEvent(
        kb_name=kb_name,
        timestamp=imported_at,
        changed_capabilities=list(capabilities.keys()),
        previous_config=None,
        new_config={k: v.model_dump() for k, v in capabilities.items()},
    )
    await emit_config_change_event(event)

    return ConfigImportResponse(
        kb_name=kb_name,
        version=result.version,
        capabilities=capabilities,
        imported_at=imported_at,
    )
