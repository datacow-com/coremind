"""
Property-based tests for Provider Configuration

Phase 1: 多云算力基础设施
Property 4: Provider Configuration Completeness
Property 5: Environment Variable Validation

Validates: Requirements 3.2, 3.4
"""
import os
import pytest
from hypothesis import given, strategies as st, assume, settings

from core.llm.provider_config import (
    ENHANCED_PROVIDER_CONFIGS,
    REQUIRED_ENV,
    validate_provider,
    get_enhanced_provider_config,
    get_all_enhanced_providers,
    get_domestic_providers,
    get_foreign_providers,
    validate_all_providers,
)


class TestProviderConfigurationCompleteness:
    """
    Property 4: Provider Configuration Completeness
    For any provider in the configuration, it should contain all required fields.
    Validates: Requirements 3.2
    """

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_provider_has_required_fields(self, provider_name: str):
        """Each provider must have all required configuration fields"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        
        # Required fields
        assert "name" in config, f"{provider_name} missing 'name'"
        assert "category" in config, f"{provider_name} missing 'category'"
        assert "priority" in config, f"{provider_name} missing 'priority'"
        assert "api_key_env" in config, f"{provider_name} missing 'api_key_env'"
        assert "models" in config, f"{provider_name} missing 'models'"
        
        # Either base_url or base_url_env must be present
        has_base_url = "base_url" in config or "base_url_env" in config
        assert has_base_url, f"{provider_name} missing 'base_url' or 'base_url_env'"

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_provider_models_have_required_fields(self, provider_name: str):
        """Each model in provider config must have required fields"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        models = config.get("models", {})
        
        for model_id, model_config in models.items():
            assert "cost_per_1k_input" in model_config, \
                f"{provider_name}/{model_id} missing 'cost_per_1k_input'"
            assert "cost_per_1k_output" in model_config, \
                f"{provider_name}/{model_id} missing 'cost_per_1k_output'"
            assert "context_length" in model_config, \
                f"{provider_name}/{model_id} missing 'context_length'"
            assert "type" in model_config, \
                f"{provider_name}/{model_id} missing 'type'"

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_provider_category_valid(self, provider_name: str):
        """Provider category must be valid"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        valid_categories = {"domestic", "foreign", "local"}
        assert config["category"] in valid_categories, \
            f"{provider_name} has invalid category: {config['category']}"

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_provider_priority_positive(self, provider_name: str):
        """Provider priority must be positive integer"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        assert isinstance(config["priority"], int), \
            f"{provider_name} priority must be int"
        assert config["priority"] > 0, \
            f"{provider_name} priority must be positive"

    @given(st.sampled_from(list(ENHANCED_PROVIDER_CONFIGS.keys())))
    @settings(max_examples=20)
    def test_get_enhanced_provider_config_returns_valid(self, provider_name: str):
        """get_enhanced_provider_config should return valid config for known providers"""
        config = get_enhanced_provider_config(provider_name)
        assert config is not None
        assert config["name"] == provider_name

    def test_get_enhanced_provider_config_unknown_returns_none(self):
        """get_enhanced_provider_config should return None for unknown providers"""
        config = get_enhanced_provider_config("unknown_provider_xyz")
        assert config is None


class TestEnvironmentVariableValidation:
    """
    Property 5: Environment Variable Validation
    For any provider, validate_provider() should correctly identify missing env vars.
    Validates: Requirements 3.4
    """

    @pytest.mark.parametrize("provider_name", list(REQUIRED_ENV.keys()))
    def test_validate_provider_returns_correct_structure(self, provider_name: str):
        """validate_provider should return dict with required keys"""
        result = validate_provider(provider_name)
        
        assert "provider" in result
        assert "required_env" in result
        assert "missing_env" in result
        assert "configured" in result
        
        assert result["provider"] == provider_name
        assert isinstance(result["required_env"], list)
        assert isinstance(result["missing_env"], list)
        assert isinstance(result["configured"], bool)

    @pytest.mark.parametrize("provider_name", list(REQUIRED_ENV.keys()))
    def test_validate_provider_missing_env_subset_of_required(self, provider_name: str):
        """missing_env should be a subset of required_env"""
        result = validate_provider(provider_name)
        
        for missing in result["missing_env"]:
            assert missing in result["required_env"], \
                f"missing_env '{missing}' not in required_env"

    @pytest.mark.parametrize("provider_name", list(REQUIRED_ENV.keys()))
    def test_validate_provider_configured_consistency(self, provider_name: str):
        """configured should be True iff missing_env is empty"""
        result = validate_provider(provider_name)
        
        if result["configured"]:
            assert len(result["missing_env"]) == 0, \
                "configured=True but missing_env is not empty"
        else:
            assert len(result["missing_env"]) > 0, \
                "configured=False but missing_env is empty"

    def test_validate_provider_ollama_no_env_required(self):
        """Ollama should require no environment variables"""
        result = validate_provider("ollama")
        assert result["required_env"] == []
        assert result["missing_env"] == []
        assert result["configured"] is True

    def test_validate_all_providers_returns_all(self):
        """validate_all_providers should return results for all enhanced providers"""
        results = validate_all_providers()
        
        for provider_name in ENHANCED_PROVIDER_CONFIGS:
            assert provider_name in results, \
                f"Missing validation result for {provider_name}"

    @given(st.sampled_from(list(REQUIRED_ENV.keys())))
    @settings(max_examples=20)
    def test_validate_provider_idempotent(self, provider_name: str):
        """validate_provider should return same result on repeated calls"""
        result1 = validate_provider(provider_name)
        result2 = validate_provider(provider_name)
        
        assert result1 == result2


class TestProviderCategoryHelpers:
    """Tests for provider category helper functions"""

    def test_get_domestic_providers_returns_domestic_only(self):
        """get_domestic_providers should return only domestic providers"""
        domestic = get_domestic_providers()
        
        for provider_name in domestic:
            config = ENHANCED_PROVIDER_CONFIGS[provider_name]
            assert config["category"] == "domestic", \
                f"{provider_name} is not domestic"

    def test_get_foreign_providers_returns_foreign_only(self):
        """get_foreign_providers should return only foreign providers"""
        foreign = get_foreign_providers()
        
        for provider_name in foreign:
            config = ENHANCED_PROVIDER_CONFIGS[provider_name]
            assert config["category"] == "foreign", \
                f"{provider_name} is not foreign"

    def test_domestic_and_foreign_disjoint(self):
        """Domestic and foreign provider sets should be disjoint"""
        domestic = set(get_domestic_providers())
        foreign = set(get_foreign_providers())
        
        intersection = domestic & foreign
        assert len(intersection) == 0, \
            f"Providers in both domestic and foreign: {intersection}"

    def test_get_all_enhanced_providers_complete(self):
        """get_all_enhanced_providers should return all configured providers"""
        all_providers = set(get_all_enhanced_providers())
        config_providers = set(ENHANCED_PROVIDER_CONFIGS.keys())
        
        assert all_providers == config_providers


class TestProviderCostConfiguration:
    """Tests for provider cost configuration consistency"""

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_model_costs_non_negative(self, provider_name: str):
        """All model costs should be non-negative"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        
        for model_id, model_config in config.get("models", {}).items():
            input_cost = model_config.get("cost_per_1k_input", 0)
            output_cost = model_config.get("cost_per_1k_output", 0)
            
            assert input_cost >= 0, \
                f"{provider_name}/{model_id} has negative input cost"
            assert output_cost >= 0, \
                f"{provider_name}/{model_id} has negative output cost"

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_context_length_positive(self, provider_name: str):
        """All model context lengths should be positive"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        
        for model_id, model_config in config.get("models", {}).items():
            context_length = model_config.get("context_length", 0)
            
            assert context_length > 0, \
                f"{provider_name}/{model_id} has non-positive context_length"

    @pytest.mark.parametrize("provider_name", list(ENHANCED_PROVIDER_CONFIGS.keys()))
    def test_model_type_valid(self, provider_name: str):
        """All model types should be valid"""
        config = ENHANCED_PROVIDER_CONFIGS[provider_name]
        valid_types = {"chat", "embedding", "vision", "rerank"}
        
        for model_id, model_config in config.get("models", {}).items():
            model_type = model_config.get("type")
            
            assert model_type in valid_types, \
                f"{provider_name}/{model_id} has invalid type: {model_type}"
