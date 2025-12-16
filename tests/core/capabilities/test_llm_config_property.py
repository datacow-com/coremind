"""
Property-based tests for LLM Gateway Configuration API

**Feature: capability-visualization, Property 5: LLM Config Round-Trip**
**Validates: Requirements 4.2, 4.3**

For any KB name and valid LLM configuration, updating the config and then
retrieving it should return an equivalent configuration.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock
import json

from server.api.llm_gateway import (
    LLMConfig,
    LLMConfigUpdateRequest,
    ProviderConfig,
    RoutingStrategyType,
    ROUTING_STRATEGIES,
    DOMESTIC_PROVIDERS,
    extract_llm_config_from_kb,
    merge_llm_config_to_kb,
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

# Valid routing strategies
routing_strategy_strategy = st.sampled_from(["default", "cost_first", "performance_first", "balanced"])

# Valid provider names
VALID_PROVIDERS = ["dashscope", "deepseek", "volcengine", "openai", "azure", "anthropic", "gemini"]
provider_name_strategy = st.sampled_from(VALID_PROVIDERS)

# Valid model names
VALID_MODELS = [
    "qwen-max", "qwen-plus", "qwen-turbo",
    "deepseek-chat", "deepseek-coder",
    "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo",
    "claude-3-5-sonnet", "claude-3-haiku",
]
model_name_strategy = st.sampled_from(VALID_MODELS)

# Budget limit strategy (positive floats or None)
budget_limit_strategy = st.one_of(
    st.none(),
    st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False),
)

# Fallback chain strategy
fallback_chain_strategy = st.lists(
    st.builds(
        lambda p, m: f"{p}/{m}",
        p=provider_name_strategy,
        m=model_name_strategy,
    ),
    min_size=0,
    max_size=5,
)

# Provider config strategy
provider_config_strategy = st.builds(
    ProviderConfig,
    enabled=st.booleans(),
    api_key=st.one_of(st.none(), st.text(min_size=10, max_size=50)),
    base_url=st.one_of(st.none(), st.just("https://api.example.com/v1")),
    timeout=st.integers(min_value=10, max_value=300),
    max_retries=st.integers(min_value=0, max_value=5),
)

# Provider configs dict strategy
provider_configs_strategy = st.dictionaries(
    keys=provider_name_strategy,
    values=provider_config_strategy,
    min_size=0,
    max_size=3,
)

# Full LLM config strategy
llm_config_strategy = st.builds(
    LLMConfig,
    routing_strategy=routing_strategy_strategy,
    budget_limit=budget_limit_strategy,
    fallback_chain=fallback_chain_strategy,
    provider_configs=provider_configs_strategy,
    default_provider=st.one_of(st.none(), provider_name_strategy),
    default_model=st.one_of(st.none(), model_name_strategy),
    enable_cost_tracking=st.booleans(),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Property Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMConfigRoundTrip:
    """
    **Feature: capability-visualization, Property 5: LLM Config Round-Trip**
    **Validates: Requirements 4.2, 4.3**
    
    For any KB name and valid LLM configuration, updating the config and then
    retrieving it should return an equivalent configuration.
    """

    @given(kb_name=kb_name_strategy, config=llm_config_strategy)
    @settings(max_examples=100)
    def test_extract_merge_roundtrip(self, kb_name: str, config: LLMConfig):
        """
        Property: Extracting LLM config from KB config and merging it back
        should preserve the LLM settings.
        """
        # Start with default KB config
        kb_config = default_kb_config(kb_name)
        
        # Merge the test LLM config into KB config
        merged_config = merge_llm_config_to_kb(kb_config.copy(), config)
        
        # Extract LLM config back
        extracted = extract_llm_config_from_kb(merged_config)
        
        # Verify round-trip: all settings should be preserved
        assert extracted.routing_strategy == config.routing_strategy, \
            f"Routing strategy changed: {config.routing_strategy} -> {extracted.routing_strategy}"
        
        assert extracted.budget_limit == config.budget_limit, \
            f"Budget limit changed: {config.budget_limit} -> {extracted.budget_limit}"
        
        assert extracted.fallback_chain == config.fallback_chain, \
            f"Fallback chain changed: {config.fallback_chain} -> {extracted.fallback_chain}"
        
        assert extracted.default_provider == config.default_provider, \
            f"Default provider changed: {config.default_provider} -> {extracted.default_provider}"
        
        assert extracted.default_model == config.default_model, \
            f"Default model changed: {config.default_model} -> {extracted.default_model}"
        
        assert extracted.enable_cost_tracking == config.enable_cost_tracking, \
            f"Cost tracking changed: {config.enable_cost_tracking} -> {extracted.enable_cost_tracking}"
        
        # Provider configs should be preserved
        for provider_id, provider_config in config.provider_configs.items():
            assert provider_id in extracted.provider_configs, \
                f"Provider config {provider_id} lost during round-trip"
            extracted_pc = extracted.provider_configs[provider_id]
            assert extracted_pc.enabled == provider_config.enabled
            assert extracted_pc.timeout == provider_config.timeout
            assert extracted_pc.max_retries == provider_config.max_retries

    @given(kb_name=kb_name_strategy)
    @settings(max_examples=50)
    def test_default_config_extraction(self, kb_name: str):
        """
        Property: Extracting LLM config from default KB config should return
        a valid LLMConfig with default values.
        """
        kb_config = default_kb_config(kb_name)
        extracted = extract_llm_config_from_kb(kb_config)
        
        # Should return a valid LLMConfig
        assert isinstance(extracted, LLMConfig)
        assert extracted.routing_strategy in ["default", "cost_first", "performance_first", "balanced"]
        assert isinstance(extracted.fallback_chain, list)
        assert isinstance(extracted.provider_configs, dict)
        assert isinstance(extracted.enable_cost_tracking, bool)

    @given(config=llm_config_strategy)
    @settings(max_examples=50)
    def test_merge_preserves_other_fields(self, config: LLMConfig):
        """
        Property: Merging LLM config should not affect other KB config fields.
        """
        kb_config = default_kb_config("test_kb")
        original_name = kb_config.get("name")
        original_stack = kb_config.get("stack")
        original_top_k = kb_config.get("top_k_default")
        original_capabilities = kb_config.get("capabilities")
        
        # Merge LLM config
        merged = merge_llm_config_to_kb(kb_config.copy(), config)
        
        # Other fields should be preserved
        assert merged.get("name") == original_name
        assert merged.get("stack") == original_stack
        assert merged.get("top_k_default") == original_top_k
        # Capabilities should not be affected
        assert merged.get("capabilities") == original_capabilities

    @given(strategy=routing_strategy_strategy)
    @settings(max_examples=20)
    def test_single_strategy_roundtrip(self, strategy: str):
        """
        Property: A single routing strategy setting should survive round-trip.
        """
        config = LLMConfig(routing_strategy=strategy)
        
        kb_config = default_kb_config("test_kb")
        merged = merge_llm_config_to_kb(kb_config.copy(), config)
        extracted = extract_llm_config_from_kb(merged)
        
        assert extracted.routing_strategy == strategy

    @given(budget=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=30)
    def test_budget_limit_roundtrip(self, budget: float):
        """
        Property: Budget limit should survive round-trip.
        """
        config = LLMConfig(budget_limit=budget)
        
        kb_config = default_kb_config("test_kb")
        merged = merge_llm_config_to_kb(kb_config.copy(), config)
        extracted = extract_llm_config_from_kb(merged)
        
        assert extracted.budget_limit == budget

    @given(chain=fallback_chain_strategy)
    @settings(max_examples=30)
    def test_fallback_chain_roundtrip(self, chain: list[str]):
        """
        Property: Fallback chain should survive round-trip.
        """
        config = LLMConfig(fallback_chain=chain)
        
        kb_config = default_kb_config("test_kb")
        merged = merge_llm_config_to_kb(kb_config.copy(), config)
        extracted = extract_llm_config_from_kb(merged)
        
        assert extracted.fallback_chain == chain


class TestLLMConfigModel:
    """Tests for LLMConfig Pydantic model."""

    def test_default_values(self):
        """LLMConfig should have sensible defaults."""
        config = LLMConfig()
        
        assert config.routing_strategy == "default"
        assert config.budget_limit is None
        assert config.fallback_chain == []
        assert config.provider_configs == {}
        assert config.default_provider is None
        assert config.default_model is None
        assert config.enable_cost_tracking is True

    @given(config=llm_config_strategy)
    @settings(max_examples=30)
    def test_model_serialization_roundtrip(self, config: LLMConfig):
        """Model should survive JSON serialization round-trip."""
        json_str = config.model_dump_json()
        restored = LLMConfig.model_validate_json(json_str)
        
        assert restored.routing_strategy == config.routing_strategy
        assert restored.budget_limit == config.budget_limit
        assert restored.fallback_chain == config.fallback_chain
        assert restored.default_provider == config.default_provider
        assert restored.default_model == config.default_model
        assert restored.enable_cost_tracking == config.enable_cost_tracking

    def test_routing_strategy_validation(self):
        """Invalid routing strategy should raise validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            LLMConfig(routing_strategy="invalid_strategy")


class TestProviderConfigModel:
    """Tests for ProviderConfig Pydantic model."""

    def test_default_values(self):
        """ProviderConfig should have sensible defaults."""
        config = ProviderConfig()
        
        assert config.enabled is True
        assert config.api_key is None
        assert config.base_url is None
        assert config.timeout == 60
        assert config.max_retries == 2

    @given(config=provider_config_strategy)
    @settings(max_examples=20)
    def test_model_serialization_roundtrip(self, config: ProviderConfig):
        """Model should survive JSON serialization round-trip."""
        json_str = config.model_dump_json()
        restored = ProviderConfig.model_validate_json(json_str)
        
        assert restored.enabled == config.enabled
        assert restored.timeout == config.timeout
        assert restored.max_retries == config.max_retries


class TestRoutingStrategies:
    """Tests for routing strategies constants."""

    def test_all_strategies_have_required_fields(self):
        """All routing strategies should have id, name, and description."""
        for strategy in ROUTING_STRATEGIES:
            assert strategy.id is not None
            assert strategy.name is not None
            assert strategy.description is not None
            assert len(strategy.name) > 0
            assert len(strategy.description) > 0

    def test_strategy_ids_are_unique(self):
        """All strategy IDs should be unique."""
        ids = [s.id for s in ROUTING_STRATEGIES]
        assert len(ids) == len(set(ids))

    def test_expected_strategies_exist(self):
        """Expected routing strategies should exist."""
        ids = {s.id for s in ROUTING_STRATEGIES}
        assert "default" in ids
        assert "cost_first" in ids
        assert "performance_first" in ids
        assert "balanced" in ids


class TestDomesticProviders:
    """Tests for domestic providers constant."""

    def test_domestic_providers_not_empty(self):
        """Domestic providers set should not be empty."""
        assert len(DOMESTIC_PROVIDERS) > 0

    def test_expected_domestic_providers(self):
        """Expected domestic providers should be in the set."""
        assert "dashscope" in DOMESTIC_PROVIDERS
        assert "deepseek" in DOMESTIC_PROVIDERS
        assert "volcengine" in DOMESTIC_PROVIDERS
