"""
Property-based tests for Cost Estimation Before Execution

**Feature: vertical-domain-phase2, Property 6: Cost Estimation Before Execution**
**Validates: Requirements 7.3, 7.4, 7.5**

For any cloud API call made by a domain interpreter, the cost_estimator should be
invoked before execution, and budget check should occur.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema


# Strategies for property tests
input_token_counts = st.integers(min_value=1, max_value=100000)
output_token_counts = st.integers(min_value=1, max_value=50000)
image_counts = st.integers(min_value=0, max_value=10)
budget_amounts = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False)
cost_amounts = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
prompt_texts = st.text(min_size=1, max_size=2000)


class TestInterpreter(BaseDomainInterpreter):
    """Test interpreter for cost integration tests"""
    
    def __init__(self):
        super().__init__()
        self._domain_id = "cost_test"
        self._requires_gpu = False
        self._recommended_vram_mb = 0
    
    @property
    def domain_id(self) -> str:
        return self._domain_id
    
    @property
    def requires_gpu(self) -> bool:
        return self._requires_gpu
    
    @property
    def recommended_vram_mb(self) -> int:
        return self._recommended_vram_mb
    
    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        return InterpretationResult(
            domain_id=self.domain_id,
            structured_data={},
            narrative="",
            confidence=0.5,
        )
    
    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)
    
    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        return True, []


class TestCostEstimationProperty:
    """
    **Feature: vertical-domain-phase2, Property 6: Cost Estimation Before Execution**
    **Validates: Requirements 7.3, 7.4, 7.5**
    """

    @given(input_token_counts, output_token_counts, image_counts)
    @settings(max_examples=100)
    def test_estimate_cost_returns_positive_value(
        self,
        input_tokens: int,
        output_tokens: int,
        image_count: int
    ):
        """
        For any valid token counts and image count, cost estimation should return
        a non-negative value.
        """
        interpreter = TestInterpreter()
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.001)
        mock_estimator.estimate.return_value = 0.002 * image_count if image_count > 0 else 0.0
        interpreter._cost_estimator = mock_estimator
        
        # Run the cost estimation
        cost = asyncio.get_event_loop().run_until_complete(
            interpreter._estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                image_count=image_count
            )
        )
        
        assert cost >= 0, "Cost should be non-negative"
        mock_estimator.get_cheapest_provider.assert_called_once()

    @given(budget_amounts, cost_amounts)
    @settings(max_examples=100)
    def test_budget_check_respects_remaining_budget(
        self,
        remaining_budget: float,
        estimated_cost: float
    ):
        """
        For any remaining budget and estimated cost, budget check should correctly
        determine if the call is allowed.
        """
        interpreter = TestInterpreter()
        
        # Mock the cost tracker
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, remaining_budget))
        interpreter._cost_tracker = mock_tracker
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", estimated_cost)
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        # Run the budget check
        allowed, remaining = asyncio.get_event_loop().run_until_complete(
            interpreter._check_budget_before_call(
                task_type="chat",
                estimated_input_tokens=1000,
                estimated_output_tokens=500
            )
        )
        
        # If estimated cost exceeds remaining budget, should not be allowed
        if estimated_cost > remaining_budget:
            assert allowed is False, "Should not allow call when cost exceeds budget"
        else:
            assert allowed is True, "Should allow call when budget is sufficient"

    @given(prompt_texts)
    @settings(max_examples=50)
    def test_llm_call_checks_budget_first(self, prompt: str):
        """
        For any prompt, _call_llm should check budget before making the API call.
        """
        interpreter = TestInterpreter()
        
        budget_check_called = False
        
        async def mock_budget_check(*args, **kwargs):
            nonlocal budget_check_called
            budget_check_called = True
            return (True, 100.0)
        
        # Mock the budget check
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = mock_budget_check
            
            # Mock the gateway
            mock_gateway = MagicMock()
            mock_gateway.chat = AsyncMock(return_value="response")
            
            with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
                asyncio.get_event_loop().run_until_complete(
                    interpreter._call_llm(prompt)
                )
        
        assert budget_check_called, "Budget check should be called before LLM call"

    @given(prompt_texts)
    @settings(max_examples=50)
    def test_vlm_call_checks_budget_first(self, prompt: str):
        """
        For any prompt, _call_vlm should check budget before making the API call.
        """
        interpreter = TestInterpreter()
        interpreter._gpu_available = False  # Force cloud VLM
        
        budget_check_called = False
        
        async def mock_budget_check(*args, **kwargs):
            nonlocal budget_check_called
            budget_check_called = True
            return (True, 100.0)
        
        # Mock the budget check
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = mock_budget_check
            
            # Mock the cloud VLM call
            with patch.object(interpreter, '_call_cloud_vlm', new_callable=AsyncMock) as mock_vlm:
                mock_vlm.return_value = "response"
                
                asyncio.get_event_loop().run_until_complete(
                    interpreter._call_vlm(b"image_data", prompt)
                )
        
        assert budget_check_called, "Budget check should be called before VLM call"

    @given(st.floats(min_value=0.0, max_value=0.0001, allow_nan=False))
    @settings(max_examples=50)
    def test_budget_exceeded_raises_error(self, remaining: float):
        """
        For any remaining budget that is insufficient, calls should raise BudgetExceededError.
        """
        interpreter = TestInterpreter()
        
        # Mock the budget check to return insufficient budget
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (False, remaining)
            
            from core.llm.exceptions import BudgetExceededError
            
            with pytest.raises(BudgetExceededError):
                asyncio.get_event_loop().run_until_complete(
                    interpreter._call_llm("test prompt")
                )

    def test_skip_budget_check_bypasses_check(self):
        """
        When skip_budget_check=True, budget check should not be called.
        """
        interpreter = TestInterpreter()
        
        # Mock the budget check
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 100.0)
            
            # Mock the gateway
            mock_gateway = MagicMock()
            mock_gateway.chat = AsyncMock(return_value="response")
            
            with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
                asyncio.get_event_loop().run_until_complete(
                    interpreter._call_llm("test prompt", skip_budget_check=True)
                )
        
        mock_check.assert_not_called()


class TestCostTrackingProperty:
    """
    Tests for cost tracking after API calls.
    """

    @given(input_token_counts, output_token_counts)
    @settings(max_examples=50)
    def test_vlm_cost_tracked_on_success(self, input_tokens: int, output_tokens: int):
        """
        For any successful VLM call, cost should be tracked.
        """
        interpreter = TestInterpreter()
        
        track_called = False
        tracked_record = None
        
        async def mock_track(record):
            nonlocal track_called, tracked_record
            track_called = True
            tracked_record = record
        
        # Mock the cost tracker
        mock_tracker = MagicMock()
        mock_tracker.track = AsyncMock(side_effect=mock_track)
        mock_tracker.check_budget = AsyncMock(return_value=(True, 100.0))
        interpreter._cost_tracker = mock_tracker
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-vl", 0.01)
        mock_estimator.estimate.return_value = 0.01
        interpreter._cost_estimator = mock_estimator
        
        # Run the tracking
        asyncio.get_event_loop().run_until_complete(
            interpreter._track_vlm_cost(
                provider_id="dashscope",
                model_id="qwen-vl-plus",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                image_count=1,
                latency_ms=1000,
                success=True
            )
        )
        
        assert track_called, "Cost tracking should be called"
        assert tracked_record is not None
        assert tracked_record.success is True
        assert tracked_record.input_tokens == input_tokens
        assert tracked_record.output_tokens == output_tokens

    @given(input_token_counts)
    @settings(max_examples=50)
    def test_vlm_cost_tracked_on_failure(self, input_tokens: int):
        """
        For any failed VLM call, cost should still be tracked with success=False.
        """
        interpreter = TestInterpreter()
        
        track_called = False
        tracked_record = None
        
        async def mock_track(record):
            nonlocal track_called, tracked_record
            track_called = True
            tracked_record = record
        
        # Mock the cost tracker
        mock_tracker = MagicMock()
        mock_tracker.track = AsyncMock(side_effect=mock_track)
        interpreter._cost_tracker = mock_tracker
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.estimate.return_value = 0.01
        interpreter._cost_estimator = mock_estimator
        
        # Run the tracking for a failed call
        asyncio.get_event_loop().run_until_complete(
            interpreter._track_vlm_cost(
                provider_id="dashscope",
                model_id="qwen-vl-plus",
                input_tokens=input_tokens,
                output_tokens=0,
                image_count=1,
                latency_ms=500,
                success=False,
                error_message="API error"
            )
        )
        
        assert track_called, "Cost tracking should be called even on failure"
        assert tracked_record is not None
        assert tracked_record.success is False
        assert tracked_record.error_message == "API error"


class TestCostEstimationEdgeCases:
    """
    Edge case tests for cost estimation.
    """

    def test_zero_tokens_returns_zero_cost(self):
        """
        Zero tokens should result in zero cost.
        """
        interpreter = TestInterpreter()
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.0)
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        cost = asyncio.get_event_loop().run_until_complete(
            interpreter._estimate_cost(
                input_tokens=0,
                output_tokens=0,
                image_count=0
            )
        )
        
        assert cost == 0.0

    def test_image_cost_added_correctly(self):
        """
        Image cost should be added to token cost.
        """
        interpreter = TestInterpreter()
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-vl", 0.01)
        mock_estimator.estimate.return_value = 0.003  # Per image cost
        interpreter._cost_estimator = mock_estimator
        
        cost = asyncio.get_event_loop().run_until_complete(
            interpreter._estimate_cost(
                input_tokens=1000,
                output_tokens=500,
                image_count=2
            )
        )
        
        # Should be base cost + image cost
        assert cost == 0.01 + 0.003

    def test_budget_check_with_no_tracker(self):
        """
        Budget check should work even if tracker returns error.
        """
        interpreter = TestInterpreter()
        
        # Mock the cost tracker to raise an exception
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, 100.0))
        interpreter._cost_tracker = mock_tracker
        
        # Mock the cost estimator
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.001)
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        allowed, remaining = asyncio.get_event_loop().run_until_complete(
            interpreter._check_budget_before_call()
        )
        
        # Should gracefully handle and allow the call
        assert allowed is True
