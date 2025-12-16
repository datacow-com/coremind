"""
LLM Gateway API - LLM 路由策略与配置 API

提供 LLM 路由策略和 KB 级别 LLM 配置管理接口：
- GET /api/llm/routing-strategies - 获取可用路由策略
- GET /api/llm/providers - 获取可用 LLM 提供商
- PUT /api/kb/{kb_name}/llm-config - 更新 KB 的 LLM 配置
- GET /api/kb/{kb_name}/llm-config - 获取 KB 的 LLM 配置

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.future import select

from core.llm.cost_estimator import get_cost_estimator
from core.storage.kb_config import load_kb_config, save_kb_config
from server.database import AsyncSessionLocal
from server.models import Provider, ModelConfig

router = APIRouter(tags=["llm-gateway"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════════

RoutingStrategyType = Literal["default", "cost_first", "performance_first", "balanced"]


class RoutingStrategy(BaseModel):
    """Routing strategy definition."""

    id: RoutingStrategyType
    name: str
    description: str


class RoutingStrategiesResponse(BaseModel):
    """Response for GET /api/llm/routing-strategies."""

    strategies: list[RoutingStrategy]


class ProviderInfo(BaseModel):
    """LLM Provider information."""

    id: str
    name: str
    category: str
    is_active: bool
    is_healthy: bool
    priority: int
    is_domestic: bool
    models: list[str] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    """Response for GET /api/llm/providers."""

    providers: list[ProviderInfo]


class ProviderConfig(BaseModel):
    """Provider-specific configuration."""

    enabled: bool = True
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 60
    max_retries: int = 2


class LLMConfig(BaseModel):
    """LLM configuration for a KB."""

    routing_strategy: RoutingStrategyType = "default"
    budget_limit: float | None = None
    fallback_chain: list[str] = Field(default_factory=list)
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=dict)
    default_provider: str | None = None
    default_model: str | None = None
    enable_cost_tracking: bool = True


class LLMConfigResponse(BaseModel):
    """Response for GET /api/kb/{kb_name}/llm-config."""

    kb_name: str
    config: LLMConfig
    current_usage: float | None = None
    updated_at: str | None = None


class LLMConfigUpdateRequest(BaseModel):
    """Request for PUT /api/kb/{kb_name}/llm-config."""

    routing_strategy: RoutingStrategyType | None = None
    budget_limit: float | None = None
    fallback_chain: list[str] | None = None
    provider_configs: dict[str, ProviderConfig] | None = None
    default_provider: str | None = None
    default_model: str | None = None
    enable_cost_tracking: bool | None = None


class LLMConfigUpdateResponse(BaseModel):
    """Response for PUT /api/kb/{kb_name}/llm-config."""

    kb_name: str
    config: LLMConfig
    updated_at: str
    applied: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

ROUTING_STRATEGIES: list[RoutingStrategy] = [
    RoutingStrategy(
        id="default",
        name="默认策略",
        description="使用配置的默认 Provider 和模型，按优先级进行故障转移",
    ),
    RoutingStrategy(
        id="cost_first",
        name="成本优先",
        description="优先选择成本最低的 Provider，适合大批量处理场景",
    ),
    RoutingStrategy(
        id="performance_first",
        name="性能优先",
        description="优先选择响应最快的 Provider，适合实时交互场景",
    ),
    RoutingStrategy(
        id="balanced",
        name="均衡策略",
        description="在成本和性能之间取得平衡，综合考虑多个因素",
    ),
]

DOMESTIC_PROVIDERS = {"dashscope", "deepseek", "volcengine", "baichuan", "zhipu"}


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def extract_llm_config_from_kb(kb_config: dict[str, Any]) -> LLMConfig:
    """Extract LLM configuration from KB config structure."""
    llm_config = kb_config.get("llm_config", {})

    return LLMConfig(
        routing_strategy=llm_config.get("routing_strategy", "default"),
        budget_limit=llm_config.get("budget_limit"),
        fallback_chain=llm_config.get("fallback_chain", []),
        provider_configs={
            k: ProviderConfig(**v) if isinstance(v, dict) else ProviderConfig()
            for k, v in llm_config.get("provider_configs", {}).items()
        },
        default_provider=llm_config.get("default_provider"),
        default_model=llm_config.get("default_model"),
        enable_cost_tracking=llm_config.get("enable_cost_tracking", True),
    )


def merge_llm_config_to_kb(
    kb_config: dict[str, Any], llm_config: LLMConfig
) -> dict[str, Any]:
    """Merge LLM configuration back into KB config structure."""
    kb_config["llm_config"] = {
        "routing_strategy": llm_config.routing_strategy,
        "budget_limit": llm_config.budget_limit,
        "fallback_chain": llm_config.fallback_chain,
        "provider_configs": {
            k: v.model_dump() for k, v in llm_config.provider_configs.items()
        },
        "default_provider": llm_config.default_provider,
        "default_model": llm_config.default_model,
        "enable_cost_tracking": llm_config.enable_cost_tracking,
    }
    return kb_config


async def get_current_usage(kb_name: str) -> float | None:
    """Get current usage for a KB from cost tracker."""
    try:
        from core.llm.cost_tracker import get_cost_tracker

        tracker = get_cost_tracker()
        summary = await tracker.get_cost_summary(channel_id=kb_name)
        return summary.get("total_cost", 0.0)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints - LLM Routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/llm/routing-strategies", response_model=RoutingStrategiesResponse)
async def get_routing_strategies() -> RoutingStrategiesResponse:
    """
    获取可用的 LLM 路由策略列表

    Requirements: 4.1
    """
    return RoutingStrategiesResponse(strategies=ROUTING_STRATEGIES)


@router.get("/llm/providers", response_model=ProvidersResponse)
async def get_llm_providers() -> ProvidersResponse:
    """
    获取可用的 LLM 提供商列表

    Requirements: 4.1
    """
    providers: list[ProviderInfo] = []

    try:
        async with AsyncSessionLocal() as session:
            # Query active LLM providers
            result = await session.execute(
                select(Provider).where(
                    Provider.category == "llm",
                    Provider.is_active == True,
                ).order_by(Provider.priority.asc())
            )
            db_providers = result.scalars().all()

            for prov in db_providers:
                # Get models for this provider
                models_result = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.provider_id == prov.id,
                        ModelConfig.is_active == True,
                    )
                )
                models = [m.model_id for m in models_result.scalars().all()]

                providers.append(
                    ProviderInfo(
                        id=prov.id,
                        name=prov.name,
                        category=prov.category,
                        is_active=prov.is_active,
                        is_healthy=prov.is_healthy,
                        priority=prov.priority,
                        is_domestic=prov.name.lower() in DOMESTIC_PROVIDERS,
                        models=models,
                    )
                )
    except Exception:
        # Fallback to cost estimator data if DB unavailable
        estimator = get_cost_estimator()
        for provider_id in estimator.DEFAULT_COSTS.keys():
            models = list(estimator.DEFAULT_COSTS[provider_id].keys())
            providers.append(
                ProviderInfo(
                    id=provider_id,
                    name=provider_id.title(),
                    category="llm",
                    is_active=True,
                    is_healthy=True,
                    priority=10,
                    is_domestic=provider_id.lower() in DOMESTIC_PROVIDERS,
                    models=models,
                )
            )

    return ProvidersResponse(providers=providers)


# ═══════════════════════════════════════════════════════════════════════════════
# API Endpoints - KB LLM Config Routes
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/kb/{kb_name}/llm-config", response_model=LLMConfigResponse)
async def get_kb_llm_config(kb_name: str) -> LLMConfigResponse:
    """
    获取 KB 的 LLM 配置

    Requirements: 4.3
    """
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e

    llm_config = extract_llm_config_from_kb(kb_config)
    current_usage = await get_current_usage(kb_name)

    return LLMConfigResponse(
        kb_name=kb_name,
        config=llm_config,
        current_usage=current_usage,
        updated_at=kb_config.get("llm_config_updated_at"),
    )


@router.put("/kb/{kb_name}/llm-config", response_model=LLMConfigUpdateResponse)
async def update_kb_llm_config(
    kb_name: str, request: LLMConfigUpdateRequest
) -> LLMConfigUpdateResponse:
    """
    更新 KB 的 LLM 配置

    配置更新后立即生效，后续请求将使用新的路由策略。

    Requirements: 4.2, 4.4
    """
    # Load existing config
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e

    # Get current LLM config
    current_config = extract_llm_config_from_kb(kb_config)

    # Update only provided fields
    if request.routing_strategy is not None:
        current_config.routing_strategy = request.routing_strategy
    if request.budget_limit is not None:
        current_config.budget_limit = request.budget_limit
    if request.fallback_chain is not None:
        current_config.fallback_chain = request.fallback_chain
    if request.provider_configs is not None:
        current_config.provider_configs = request.provider_configs
    if request.default_provider is not None:
        current_config.default_provider = request.default_provider
    if request.default_model is not None:
        current_config.default_model = request.default_model
    if request.enable_cost_tracking is not None:
        current_config.enable_cost_tracking = request.enable_cost_tracking

    # Validate fallback chain if provided
    if current_config.fallback_chain:
        estimator = get_cost_estimator()
        valid_providers = set(estimator.DEFAULT_COSTS.keys())
        for provider in current_config.fallback_chain:
            # Extract provider name from "provider/model" format
            provider_name = provider.split("/")[0].lower()
            if provider_name not in valid_providers:
                # Try to check in DB
                try:
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(
                            select(Provider).where(
                                Provider.name.ilike(provider_name),
                                Provider.is_active == True,
                            )
                        )
                        if not result.scalars().first():
                            raise HTTPException(
                                status_code=400,
                                detail=f"Invalid provider in fallback chain: {provider}",
                            )
                except HTTPException:
                    raise
                except Exception:
                    pass  # DB unavailable, skip validation

    # Merge back to KB config
    kb_config = merge_llm_config_to_kb(kb_config, current_config)

    # Update timestamp
    updated_at = datetime.utcnow().isoformat() + "Z"
    kb_config["llm_config_updated_at"] = updated_at

    # Save config
    try:
        save_kb_config(kb_name, kb_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}") from e

    # Configuration is applied immediately - the LLMGateway reads from KB config
    # on each request, so no additional action needed for immediate effect

    return LLMConfigUpdateResponse(
        kb_name=kb_name,
        config=current_config,
        updated_at=updated_at,
        applied=True,
    )
