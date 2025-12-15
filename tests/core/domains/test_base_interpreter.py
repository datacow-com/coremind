"""
Unit tests for BaseDomainInterpreter

**Validates: Requirements 2.1, 2.2, 2.4, 7.1**
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError


class ConcreteInterpreter(BaseDomainInterpreter):
    """Concrete implementation for testing"""
    domain_id = "test"
    requires_gpu = False
    recommended_vram_mb = 0

    async def interpret(self, document: dict, config: dict | None = None) -> InterpretationResult:
        return InterpretationResult(
            domain_id=self.domain_id,
            structured_data=document.get("data", {}),
            narrative="Test narrative",
            confidence=0.9,
        )

    def get_ontology(self) -> OntologySchema:
        return OntologySchema(domain_id=self.domain_id)

    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        if not result.structured_data:
            return False, ["structured_data is empty"]
        return True, []


class GPUInterpreter(BaseDomainInterpreter):
    """GPU-requiring interpreter for testing"""
    domain_id = "gpu_test"
    requires_gpu = True
    recommended_vram_mb = 4096

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


class TestBaseDomainInterpreterBasics:
    """Basic interpreter tests"""

    def test_interpreter_has_domain_id(self):
        """Test interpreter has domain_id"""
        interpreter = ConcreteInterpreter()
        assert interpreter.domain_id == "test"

    def test_interpreter_has_gpu_attributes(self):
        """Test interpreter has GPU attributes"""
        interpreter = GPUInterpreter()
        assert interpreter.requires_gpu is True
        assert interpreter.recommended_vram_mb == 4096

    @pytest.mark.asyncio
    async def test_interpret_returns_result(self):
        """Test interpret returns InterpretationResult"""
        interpreter = ConcreteInterpreter()
        
        result = await interpreter.interpret({"data": {"key": "value"}})
        
        assert isinstance(result, InterpretationResult)
        assert result.domain_id == "test"
        assert result.structured_data == {"key": "value"}

    def test_get_ontology_returns_schema(self):
        """Test get_ontology returns OntologySchema"""
        interpreter = ConcreteInterpreter()
        
        ontology = interpreter.get_ontology()
        
        assert isinstance(ontology, OntologySchema)
        assert ontology.domain_id == "test"

    def test_validate_output_returns_tuple(self):
        """Test validate_output returns tuple"""
        interpreter = ConcreteInterpreter()
        result = InterpretationResult(
            domain_id="test",
            structured_data={"key": "value"},
            narrative="",
            confidence=0.5,
        )
        
        valid, violations = interpreter.validate_output(result)
        
        assert isinstance(valid, bool)
        assert isinstance(violations, list)

    def test_validate_output_detects_invalid(self):
        """Test validate_output detects invalid result"""
        interpreter = ConcreteInterpreter()
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=0.5,
        )
        
        valid, violations = interpreter.validate_output(result)
        
        assert valid is False
        assert len(violations) > 0


class TestGPUAvailabilityCheck:
    """Tests for GPU availability checking"""

    def test_check_gpu_available_no_torch(self):
        """Test GPU check when torch not available"""
        interpreter = GPUInterpreter()
        
        with patch.dict('sys.modules', {'torch': None}):
            # Force reimport check
            interpreter._gpu_available = None
            result = interpreter._check_gpu_available()
        
        # Should return False when torch import fails
        assert result is False

    def test_check_gpu_available_caches_result(self):
        """Test GPU check caches result"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = True
        
        # Should return cached value without checking
        result = interpreter._check_gpu_available()
        
        assert result is True

    def test_check_gpu_available_with_mock_torch(self):
        """Test GPU check with mocked torch"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = None
        
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.current_device.return_value = 0
        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024  # 8GB
        mock_props.name = "Test GPU"
        mock_torch.cuda.get_device_properties.return_value = mock_props
        # Free memory is 6GB (more than 80% of 4GB required)
        mock_torch.cuda.mem_get_info.return_value = (6 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024)
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._check_gpu_available()
        
        assert result is True

    def test_check_gpu_insufficient_vram(self):
        """Test GPU check with insufficient VRAM"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = None
        
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.current_device.return_value = 0
        mock_props = MagicMock()
        mock_props.total_memory = 2 * 1024 * 1024 * 1024  # 2GB < 4GB required
        mock_torch.cuda.get_device_properties.return_value = mock_props
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._check_gpu_available()
        
        assert result is False


class TestLLMIntegration:
    """Tests for LLM/VLM integration"""

    @pytest.mark.asyncio
    async def test_call_llm_uses_gateway(self):
        """Test _call_llm uses LLMGateway"""
        interpreter = ConcreteInterpreter()
        
        mock_gateway = MagicMock()
        mock_gateway.chat = AsyncMock(return_value="LLM response")
        
        with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
            result = await interpreter._call_llm("test prompt")
        
        assert result == "LLM response"
        mock_gateway.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_llm_with_context(self):
        """Test _call_llm passes context"""
        interpreter = ConcreteInterpreter()
        
        mock_gateway = MagicMock()
        mock_gateway.chat = AsyncMock(return_value="response")
        
        with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
            await interpreter._call_llm("prompt", context="context")
        
        mock_gateway.chat.assert_called_once_with("prompt", "context")

    @pytest.mark.asyncio
    async def test_call_llm_raises_on_error(self):
        """Test _call_llm raises DomainInterpretationError on failure"""
        interpreter = ConcreteInterpreter()
        
        mock_gateway = MagicMock()
        mock_gateway.chat = AsyncMock(side_effect=Exception("API error"))
        
        with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
            with pytest.raises(DomainInterpretationError) as exc_info:
                await interpreter._call_llm("prompt")
        
        assert exc_info.value.stage == "llm_call"
        assert "API error" in str(exc_info.value)


class TestCostEstimation:
    """Tests for cost estimation"""

    @pytest.mark.asyncio
    async def test_estimate_cost_uses_estimator(self):
        """Test _estimate_cost uses CostEstimator"""
        interpreter = ConcreteInterpreter()
        
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.001)
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        cost = await interpreter._estimate_cost(1000, 500)
        
        assert cost == 0.001
        mock_estimator.get_cheapest_provider.assert_called_once()

    @pytest.mark.asyncio
    async def test_estimate_cost_with_images(self):
        """Test _estimate_cost includes image cost"""
        interpreter = ConcreteInterpreter()
        
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-vl", 0.001)
        mock_estimator.estimate.return_value = 0.003  # Image cost
        interpreter._cost_estimator = mock_estimator
        
        cost = await interpreter._estimate_cost(1000, 500, image_count=2)
        
        assert cost == 0.001 + 0.003  # Base + image cost


class TestGPUManagement:
    """
    Tests for GPU management features
    
    **Validates: Requirements 7.1, 7.2**
    """

    def test_should_use_cloud_vlm_when_no_gpu_required(self):
        """Non-GPU interpreters should always use cloud VLM"""
        interpreter = ConcreteInterpreter()
        
        result = interpreter._should_use_cloud_vlm()
        
        assert result is True

    def test_should_use_cloud_vlm_when_gpu_unavailable(self):
        """GPU interpreters should use cloud when GPU unavailable"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = False
        
        result = interpreter._should_use_cloud_vlm()
        
        assert result is True

    def test_should_use_local_when_gpu_available(self):
        """GPU interpreters should use local when GPU available"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = True
        
        result = interpreter._should_use_cloud_vlm()
        
        assert result is False

    def test_force_recheck_gpu(self):
        """Force recheck should ignore cached value"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = True
        
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._check_gpu_available(force_recheck=True)
        
        assert result is False

    def test_gpu_check_with_free_memory(self):
        """GPU check should consider free memory"""
        interpreter = GPUInterpreter()
        interpreter._gpu_available = None
        
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.current_device.return_value = 0
        mock_props = MagicMock()
        mock_props.total_memory = 8 * 1024 * 1024 * 1024  # 8GB total
        mock_props.name = "Test GPU"
        mock_torch.cuda.get_device_properties.return_value = mock_props
        # Free memory is only 2GB (less than 80% of 4GB required)
        mock_torch.cuda.mem_get_info.return_value = (2 * 1024 * 1024 * 1024, 8 * 1024 * 1024 * 1024)
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._check_gpu_available()
        
        assert result is False


class TestCostIntegration:
    """
    Tests for cost tracking integration
    
    **Validates: Requirements 7.3, 7.4, 7.5**
    """

    @pytest.mark.asyncio
    async def test_check_budget_before_call(self):
        """Test budget check before API call"""
        interpreter = ConcreteInterpreter()
        
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, 50.0))
        interpreter._cost_tracker = mock_tracker
        
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.01)
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        allowed, remaining = await interpreter._check_budget_before_call()
        
        assert allowed is True
        assert remaining == 50.0

    @pytest.mark.asyncio
    async def test_check_budget_blocks_when_exceeded(self):
        """Test budget check blocks when cost exceeds remaining"""
        interpreter = ConcreteInterpreter()
        
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, 0.001))  # Very low budget
        interpreter._cost_tracker = mock_tracker
        
        mock_estimator = MagicMock()
        mock_estimator.get_cheapest_provider.return_value = ("dashscope", "qwen-turbo", 0.01)  # Higher cost
        mock_estimator.estimate.return_value = 0.0
        interpreter._cost_estimator = mock_estimator
        
        allowed, remaining = await interpreter._check_budget_before_call()
        
        assert allowed is False

    @pytest.mark.asyncio
    async def test_track_vlm_cost(self):
        """Test VLM cost tracking"""
        interpreter = ConcreteInterpreter()
        
        mock_tracker = MagicMock()
        mock_tracker.track = AsyncMock()
        interpreter._cost_tracker = mock_tracker
        
        mock_estimator = MagicMock()
        mock_estimator.estimate.return_value = 0.01
        interpreter._cost_estimator = mock_estimator
        
        await interpreter._track_vlm_cost(
            provider_id="dashscope",
            model_id="qwen-vl-plus",
            input_tokens=1000,
            output_tokens=500,
            image_count=1,
            latency_ms=1000,
            success=True
        )
        
        mock_tracker.track.assert_called_once()
        call_args = mock_tracker.track.call_args[0][0]
        assert call_args.provider_id == "dashscope"
        assert call_args.model_id == "qwen-vl-plus"
        assert call_args.success is True

    @pytest.mark.asyncio
    async def test_llm_call_with_budget_check(self):
        """Test LLM call includes budget check"""
        interpreter = ConcreteInterpreter()
        
        budget_checked = False
        
        async def mock_budget_check(*args, **kwargs):
            nonlocal budget_checked
            budget_checked = True
            return (True, 100.0)
        
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = mock_budget_check
            
            mock_gateway = MagicMock()
            mock_gateway.chat = AsyncMock(return_value="response")
            
            with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
                await interpreter._call_llm("test prompt")
        
        assert budget_checked is True

    @pytest.mark.asyncio
    async def test_llm_call_skip_budget_check(self):
        """Test LLM call can skip budget check"""
        interpreter = ConcreteInterpreter()
        
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_gateway = MagicMock()
            mock_gateway.chat = AsyncMock(return_value="response")
            
            with patch('core.llm.gateway.LLMGateway', return_value=mock_gateway):
                await interpreter._call_llm("test prompt", skip_budget_check=True)
        
        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_vlm_call_with_budget_check(self):
        """Test VLM call includes budget check"""
        interpreter = ConcreteInterpreter()
        interpreter._gpu_available = False
        
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 100.0)
            
            with patch.object(interpreter, '_call_cloud_vlm', new_callable=AsyncMock) as mock_vlm:
                mock_vlm.return_value = "response"
                
                await interpreter._call_vlm(b"image", "prompt")
        
        mock_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_budget_exceeded_raises_error(self):
        """Test budget exceeded raises BudgetExceededError"""
        interpreter = ConcreteInterpreter()
        
        with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (False, 0.0)
            
            from core.llm.exceptions import BudgetExceededError
            
            with pytest.raises(BudgetExceededError):
                await interpreter._call_llm("test prompt")


class TestInterpretationResult:
    """Tests for InterpretationResult dataclass"""

    def test_result_creation(self):
        """Test creating InterpretationResult"""
        result = InterpretationResult(
            domain_id="test",
            structured_data={"key": "value"},
            narrative="Test narrative",
            confidence=0.85,
            metadata={"model": "test-model"},
            raw_elements=[{"type": "element"}],
        )
        
        assert result.domain_id == "test"
        assert result.structured_data == {"key": "value"}
        assert result.narrative == "Test narrative"
        assert result.confidence == 0.85
        assert result.metadata == {"model": "test-model"}
        assert result.raw_elements == [{"type": "element"}]

    def test_result_defaults(self):
        """Test InterpretationResult defaults"""
        result = InterpretationResult(
            domain_id="test",
            structured_data={},
            narrative="",
            confidence=0.5,
        )
        
        assert result.metadata == {}
        assert result.raw_elements == []

    def test_result_invalid_confidence_low(self):
        """Test InterpretationResult rejects confidence < 0"""
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            InterpretationResult(
                domain_id="test",
                structured_data={},
                narrative="",
                confidence=-0.1,
            )

    def test_result_invalid_confidence_high(self):
        """Test InterpretationResult rejects confidence > 1"""
        with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
            InterpretationResult(
                domain_id="test",
                structured_data={},
                narrative="",
                confidence=1.1,
            )

    def test_result_empty_domain_id(self):
        """Test InterpretationResult rejects empty domain_id"""
        with pytest.raises(ValueError, match="domain_id cannot be empty"):
            InterpretationResult(
                domain_id="",
                structured_data={},
                narrative="",
                confidence=0.5,
            )
