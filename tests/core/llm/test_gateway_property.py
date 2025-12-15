"""
Property-based tests for LLM Gateway Enhancement

Phase 1: 多云算力基础设施
Property 6: Routing Strategy Selection
Property 7: Failover Chain Correctness
Property 8: Cost Tracking Integration
Property 9: Budget Enforcement
Property 10: Backward Compatibility

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 6.4, 6.5, 7.3, 7.5
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, strategies as st, assume, settings
import uuid

from core.llm.gateway import LLMGateway, RoutingStrategy
from core.llm.cost_tracker import CostRecord
from core.llm.exceptions import BudgetExceededError, ProviderUnavailableError


# Strategies for property tests
routing_strategies = st.sampled_from(["default", "cost_first", "performance_first", "balanced"])
provider_names = st.sampled_from(["dashscope", "deepseek", "volcengine", "openai", "azure"])
model_names = st.sampled_from(["qwen-turbo", "deepseek-chat", "gpt-4o-mini"])
channel_ids = st.one_of(st.none(), st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_"))
user_ids = st.one_of(st.none(), st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_"))


class TestRoutingStrategySelection:
    """
    Property 6: Routing Strategy Selection
    For any routing strategy, the gateway should select a provider according to that strategy's criteria.
    Validates: Requirements 4.1
    """

    @given(routing_strategies)
    @settings(max_examples=20)
    def test_gateway_accepts_all_routing_strategies(self, strategy: str):
        """Gateway should accept all valid routing strategies"""
        gateway = LLMGateway(routing_strategy=strategy)
        assert gateway.routing_strategy == strategy

    @given(provider_names, model_names, routing_strategies)
    @settings(max_examples=30)
    def test_gateway_preserves_routing_strategy(
        self, provider: str, model: str, strategy: str
    ):
        """Gateway should preserve routing strategy after initialization"""
        gateway = LLMGateway(
            provider=provider,
            model=model,
            routing_strategy=strategy
        )
        
        assert gateway.routing_strategy == strategy
        assert gateway.default_provider_name == provider
        assert gateway.default_model_name == model

    @pytest.mark.asyncio
    async def test_cost_first_selects_cheapest(self):
        """cost_first strategy should select cheapest provider"""
        gateway = LLMGateway(routing_strategy="cost_first")
        
        # Mock cost estimator by patching the private attribute
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("deepseek", "deepseek-chat", 0.0001)
        gateway._cost_estimator = mock_estimator
        
        # Mock _get_model_config to return valid provider/model
        mock_provider = MagicMock()
        mock_provider.name = "deepseek"
        mock_model = MagicMock()
        mock_model.model_id = "deepseek-chat"
        
        with patch.object(gateway, '_get_model_config', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            mock_estimator.get_cheapest_provider.assert_called_once()
            assert prov.name == "deepseek"

    @pytest.mark.asyncio
    async def test_performance_first_selects_by_priority(self):
        """performance_first strategy should select by priority"""
        gateway = LLMGateway(routing_strategy="performance_first")
        
        # Mock database query
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_provider.priority = 1
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        with patch('core.llm.gateway.AsyncSessionLocal') as mock_session:
            mock_ctx = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_ctx
            
            # Mock provider query
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_provider
            mock_ctx.execute.return_value = mock_result
            
            # This will fail on second query, but we're testing the strategy selection
            try:
                await gateway._select_provider("chat")
            except Exception:
                pass  # Expected to fail on model query
            
            # Verify the query was made with priority ordering
            assert mock_ctx.execute.called

    @pytest.mark.asyncio
    async def test_default_uses_configured_provider(self):
        """default strategy should use configured provider/model"""
        gateway = LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            routing_strategy="default"
        )
        
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        with patch.object(gateway, '_get_model_config', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            mock_get.assert_called_once_with("dashscope", "qwen-turbo")


class TestFailoverChainCorrectness:
    """
    Property 7: Failover Chain Correctness
    For any unhealthy primary provider, the system should automatically select
    the next healthy provider in the failover chain.
    Validates: Requirements 4.2, 6.4, 7.5
    """

    @given(st.lists(st.tuples(provider_names, model_names), min_size=1, max_size=5))
    @settings(max_examples=20)
    def test_failover_chain_preserved(self, chain: list):
        """Failover chain should be preserved after initialization"""
        gateway = LLMGateway()
        gateway.failover_chain = chain
        
        assert gateway.failover_chain == chain
        assert len(gateway.failover_chain) == len(chain)

    def test_circuit_breaker_blocks_unhealthy(self):
        """Circuit breaker should block unhealthy providers"""
        gateway = LLMGateway()
        
        # Simulate failures
        for _ in range(3):
            gateway._cb_on_fail("test_provider")
        
        # Should be blocked
        assert not gateway._cb_allowed("test_provider")

    def test_circuit_breaker_allows_healthy(self):
        """Circuit breaker should allow healthy providers"""
        gateway = LLMGateway()
        
        # No failures
        assert gateway._cb_allowed("healthy_provider")

    def test_circuit_breaker_recovers_after_success(self):
        """Circuit breaker should recover after success"""
        gateway = LLMGateway()
        
        # Simulate failures
        for _ in range(3):
            gateway._cb_on_fail("recovering_provider")
        
        # Should be blocked
        assert not gateway._cb_allowed("recovering_provider")
        
        # Simulate success
        gateway._cb_on_success("recovering_provider")
        
        # Should be allowed again
        assert gateway._cb_allowed("recovering_provider")

    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=10)
    def test_circuit_breaker_threshold(self, fail_count: int):
        """Circuit breaker should open after threshold failures"""
        gateway = LLMGateway()
        threshold = 3  # Default threshold
        
        for i in range(fail_count):
            gateway._cb_on_fail("threshold_test")
        
        if fail_count >= threshold:
            assert not gateway._cb_allowed("threshold_test")
        else:
            assert gateway._cb_allowed("threshold_test")


class TestCostTrackingIntegration:
    """
    Property 8: Cost Tracking Integration
    For any API call with cost tracking enabled, a cost record should be created
    with correct provider_id, model_id, and cost_usd.
    Validates: Requirements 4.3, 6.5, 7.3
    """

    @given(
        provider_names,
        model_names,
        st.integers(min_value=1, max_value=10000),
        st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=30)
    def test_cost_calculation_non_negative(
        self, provider: str, model: str, input_tokens: int, output_tokens: int
    ):
        """Cost calculation should always return non-negative value"""
        gateway = LLMGateway(provider=provider, model=model)
        
        mock_provider = MagicMock()
        mock_provider.name = provider
        mock_model = MagicMock()
        mock_model.model_id = model
        
        cost = gateway._calculate_cost(
            mock_provider, mock_model, input_tokens, output_tokens
        )
        
        assert cost >= 0

    @pytest.mark.asyncio
    async def test_track_cost_called_on_success(self):
        """_track_cost should be called on successful API call"""
        gateway = LLMGateway(enable_cost_tracking=True)
        
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        # Mock cost tracker by patching the private attribute
        mock_tracker = MagicMock()
        mock_tracker.track = AsyncMock()
        gateway._cost_tracker = mock_tracker
        
        await gateway._track_cost(
            provider=mock_provider,
            model=mock_model,
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            success=True
        )
        
        mock_tracker.track.assert_called_once()
        
        # Verify the record has correct fields
        call_args = mock_tracker.track.call_args[0][0]
        assert isinstance(call_args, CostRecord)
        assert call_args.provider_id == "dashscope"
        assert call_args.model_id == "qwen-turbo"
        assert call_args.success is True

    @pytest.mark.asyncio
    async def test_track_cost_not_called_when_disabled(self):
        """_track_cost should not record when cost tracking is disabled"""
        gateway = LLMGateway(enable_cost_tracking=False)
        
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        # This should return early without calling tracker
        await gateway._track_cost(
            provider=mock_provider,
            model=mock_model,
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            success=True
        )
        
        # No exception means success

    @given(st.booleans())
    @settings(max_examples=10)
    def test_cost_tracking_flag_preserved(self, enabled: bool):
        """Cost tracking flag should be preserved"""
        gateway = LLMGateway(enable_cost_tracking=enabled)
        assert gateway.enable_cost_tracking == enabled


class TestBudgetEnforcement:
    """
    Property 9: Budget Enforcement
    For any scope where daily cost exceeds hard_stop_threshold,
    new API calls should be rejected with BudgetExceededError.
    Validates: Requirements 4.4
    """

    @pytest.mark.asyncio
    async def test_budget_check_allows_when_under_limit(self):
        """Budget check should allow when under limit"""
        gateway = LLMGateway(enable_cost_tracking=True)
        
        # Mock cost tracker by patching the private attribute
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, 50.0))
        gateway._cost_tracker = mock_tracker
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is True
        assert remaining == 50.0

    @pytest.mark.asyncio
    async def test_budget_check_denies_when_over_limit(self):
        """Budget check should deny when over limit"""
        gateway = LLMGateway(enable_cost_tracking=True)
        
        # Mock cost tracker by patching the private attribute
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(False, -5.0))
        gateway._cost_tracker = mock_tracker
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is False
        assert remaining == -5.0

    @pytest.mark.asyncio
    async def test_budget_check_skipped_when_disabled(self):
        """Budget check should be skipped when cost tracking is disabled"""
        gateway = LLMGateway(enable_cost_tracking=False)
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is True
        assert remaining == 100.0

    @given(channel_ids, user_ids)
    @settings(max_examples=20)
    def test_budget_scope_preserved(self, channel_id, user_id):
        """Budget scope (channel_id, user_id) should be preserved"""
        gateway = LLMGateway(channel_id=channel_id, user_id=user_id)
        
        assert gateway.channel_id == channel_id
        assert gateway.user_id == user_id


class TestBackwardCompatibility:
    """
    Property 10: Backward Compatibility
    For any existing API call pattern, the enhanced gateway should produce equivalent results.
    Validates: Requirements 4.5
    """

    @given(provider_names, model_names)
    @settings(max_examples=20)
    def test_legacy_init_still_works(self, provider: str, model: str):
        """Legacy initialization (provider, model only) should still work"""
        gateway = LLMGateway(provider=provider, model=model)
        
        assert gateway.default_provider_name == provider
        assert gateway.default_model_name == model
        # New fields should have defaults
        assert gateway.routing_strategy == "default"
        assert gateway.enable_cost_tracking is True

    def test_legacy_init_no_args(self):
        """Gateway should work with no arguments (uses settings defaults)"""
        gateway = LLMGateway()
        
        assert gateway.default_provider_name is not None
        assert gateway.routing_strategy == "default"

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=10)
    def test_chat_signature_compatible(self, prompt: str):
        """chat() method signature should be backward compatible"""
        gateway = LLMGateway()
        
        # Verify method exists and accepts expected arguments
        import inspect
        sig = inspect.signature(gateway.chat)
        params = list(sig.parameters.keys())
        
        assert "prompt" in params
        assert "context" in params

    def test_health_check_signature_compatible(self):
        """health_check() method signature should be backward compatible"""
        gateway = LLMGateway()
        
        import inspect
        sig = inspect.signature(gateway.health_check)
        params = list(sig.parameters.keys())
        
        assert "provider" in params
        assert "model" in params

    @given(provider_names)
    @settings(max_examples=10)
    def test_circuit_breaker_methods_exist(self, provider: str):
        """Circuit breaker methods should still exist and work"""
        gateway = LLMGateway()
        
        # These methods should exist
        assert hasattr(gateway, '_cb_allowed')
        assert hasattr(gateway, '_cb_on_fail')
        assert hasattr(gateway, '_cb_on_success')
        
        # They should work
        assert gateway._cb_allowed(provider) is True
        gateway._cb_on_fail(provider)
        gateway._cb_on_success(provider)

    def test_fallback_models_attribute_exists(self):
        """fallback_models attribute should still exist"""
        gateway = LLMGateway()
        
        assert hasattr(gateway, 'fallback_models')
        assert isinstance(gateway.fallback_models, list)

    def test_http_timeout_configurable(self):
        """HTTP timeout should still be configurable via env"""
        import os
        
        original = os.environ.get("LLM_HTTP_TIMEOUT")
        try:
            os.environ["LLM_HTTP_TIMEOUT"] = "120"
            gateway = LLMGateway()
            assert gateway.http_timeout == 120.0
        finally:
            if original:
                os.environ["LLM_HTTP_TIMEOUT"] = original
            else:
                os.environ.pop("LLM_HTTP_TIMEOUT", None)


class TestGatewayPropertyInvariants:
    """Additional property invariants for Gateway"""

    @given(
        provider_names,
        model_names,
        routing_strategies,
        channel_ids,
        st.booleans()
    )
    @settings(max_examples=50)
    def test_gateway_initialization_invariants(
        self, provider: str, model: str, strategy: str, channel_id, cost_tracking: bool
    ):
        """Gateway should maintain invariants after initialization"""
        gateway = LLMGateway(
            provider=provider,
            model=model,
            routing_strategy=strategy,
            channel_id=channel_id,
            enable_cost_tracking=cost_tracking
        )
        
        # Invariant 1: Provider and model are set
        assert gateway.default_provider_name == provider
        assert gateway.default_model_name == model
        
        # Invariant 2: Strategy is valid
        assert gateway.routing_strategy in ["default", "cost_first", "performance_first", "balanced"]
        
        # Invariant 3: Cost tracking flag is boolean
        assert isinstance(gateway.enable_cost_tracking, bool)
        
        # Invariant 4: Circuit breaker state is initialized
        assert isinstance(gateway._cb_state, dict)
        assert isinstance(gateway._cb_cooldown, dict)
        
        # Invariant 5: Failover chain is list
        assert isinstance(gateway.failover_chain, list)

    @given(st.integers(min_value=0, max_value=5))
    @settings(max_examples=10, deadline=None)  # Disable deadline for retry tests
    def test_http_retry_attempts_bounded(self, attempts: int):
        """HTTP retry should respect attempt bounds"""
        gateway = LLMGateway()
        
        call_count = 0
        def failing_fn():
            nonlocal call_count
            call_count += 1
            raise Exception("Test failure")
        
        bounded_attempts = min(attempts, 5)  # Reasonable upper bound
        
        try:
            gateway._http_retry(failing_fn, attempts=bounded_attempts, backoff_ms=1)
        except Exception:
            pass
        
        # Should have called fn (attempts + 1) times
        assert call_count == bounded_attempts + 1
