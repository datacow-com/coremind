"""
Property-based tests for GPU Fallback to Cloud Provider

**Feature: vertical-domain-phase2, Property 5: GPU Fallback to Cloud Provider**
**Validates: Requirements 1.5, 7.2**

For any domain interpreter that requires GPU, when GPU is unavailable, the system
should automatically route VLM calls to cloud providers using Phase 1 infrastructure.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema


# Strategies for property tests
vram_requirements = st.integers(min_value=1024, max_value=32768)  # 1GB to 32GB
available_vram = st.integers(min_value=0, max_value=65536)  # 0 to 64GB
prompt_texts = st.text(min_size=1, max_size=500)


class GPURequiringInterpreter(BaseDomainInterpreter):
    """Test interpreter that requires GPU"""
    
    def __init__(self, vram_mb: int = 4096):
        super().__init__()
        self._domain_id = "gpu_test"
        self._requires_gpu = True
        self._recommended_vram_mb = vram_mb
    
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


class NonGPUInterpreter(BaseDomainInterpreter):
    """Test interpreter that does not require GPU"""
    
    def __init__(self):
        super().__init__()
        self._domain_id = "non_gpu_test"
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


class TestGPUFallbackProperty:
    """
    **Feature: vertical-domain-phase2, Property 5: GPU Fallback to Cloud Provider**
    **Validates: Requirements 1.5, 7.2**
    """

    @given(vram_requirements)
    @settings(max_examples=100)
    def test_no_cuda_always_uses_cloud(self, vram_mb: int):
        """
        For any VRAM requirement, when CUDA is not available, 
        _should_use_cloud_vlm should return True.
        """
        interpreter = GPURequiringInterpreter(vram_mb=vram_mb)
        interpreter._gpu_available = None  # Reset cache
        
        # Mock torch to simulate no CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._should_use_cloud_vlm()
        
        assert result is True, "Should use cloud VLM when CUDA is not available"

    @given(vram_requirements, available_vram)
    @settings(max_examples=100)
    def test_insufficient_vram_uses_cloud(self, required_vram: int, available: int):
        """
        For any VRAM requirement, when available VRAM is less than required,
        _should_use_cloud_vlm should return True.
        """
        assume(available < required_vram)  # Only test insufficient VRAM cases
        
        interpreter = GPURequiringInterpreter(vram_mb=required_vram)
        interpreter._gpu_available = None  # Reset cache
        
        # Mock torch to simulate insufficient VRAM
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.current_device.return_value = 0
        mock_props = MagicMock()
        mock_props.total_memory = available * 1024 * 1024  # Convert MB to bytes
        mock_props.name = "Test GPU"
        mock_torch.cuda.get_device_properties.return_value = mock_props
        mock_torch.cuda.mem_get_info.return_value = (available * 1024 * 1024, available * 1024 * 1024)
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._should_use_cloud_vlm()
        
        assert result is True, f"Should use cloud VLM when VRAM ({available}MB) < required ({required_vram}MB)"

    @given(vram_requirements, available_vram)
    @settings(max_examples=100)
    def test_sufficient_vram_uses_local(self, required_vram: int, available: int):
        """
        For any VRAM requirement, when available VRAM is sufficient,
        _should_use_cloud_vlm should return False (use local GPU).
        """
        # Ensure available VRAM is at least 80% more than required (to pass free memory check)
        assume(available >= required_vram * 1.25)
        
        interpreter = GPURequiringInterpreter(vram_mb=required_vram)
        interpreter._gpu_available = None  # Reset cache
        
        # Mock torch to simulate sufficient VRAM
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.current_device.return_value = 0
        mock_props = MagicMock()
        mock_props.total_memory = available * 1024 * 1024  # Convert MB to bytes
        mock_props.name = "Test GPU"
        mock_torch.cuda.get_device_properties.return_value = mock_props
        mock_torch.cuda.mem_get_info.return_value = (available * 1024 * 1024, available * 1024 * 1024)
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._should_use_cloud_vlm()
        
        assert result is False, f"Should use local GPU when VRAM ({available}MB) >= required ({required_vram}MB)"

    def test_non_gpu_interpreter_always_uses_cloud(self):
        """
        For interpreters that don't require GPU, _should_use_cloud_vlm should return True.
        """
        interpreter = NonGPUInterpreter()
        
        result = interpreter._should_use_cloud_vlm()
        
        assert result is True, "Non-GPU interpreters should always use cloud VLM"

    @given(vram_requirements)
    @settings(max_examples=50)
    def test_torch_import_error_uses_cloud(self, vram_mb: int):
        """
        For any VRAM requirement, when torch is not installed,
        _should_use_cloud_vlm should return True.
        """
        interpreter = GPURequiringInterpreter(vram_mb=vram_mb)
        interpreter._gpu_available = None  # Reset cache
        
        # Simulate torch import failure by removing it from sys.modules
        # and making the import raise an error
        import sys
        import builtins
        
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == 'torch':
                raise ImportError("No module named 'torch'")
            return original_import(name, *args, **kwargs)
        
        # Remove torch from sys.modules if present
        torch_module = sys.modules.pop('torch', None)
        
        try:
            with patch.object(builtins, '__import__', mock_import):
                result = interpreter._should_use_cloud_vlm()
        finally:
            # Restore torch module if it was present
            if torch_module is not None:
                sys.modules['torch'] = torch_module
        
        assert result is True, "Should use cloud VLM when torch is not installed"

    @given(vram_requirements)
    @settings(max_examples=50)
    def test_gpu_check_caches_result(self, vram_mb: int):
        """
        For any VRAM requirement, GPU check result should be cached.
        """
        interpreter = GPURequiringInterpreter(vram_mb=vram_mb)
        
        # Set cached value
        interpreter._gpu_available = True
        
        # Should return cached value without checking
        result = interpreter._check_gpu_available()
        
        assert result is True, "Should return cached GPU availability"
        
        # Set different cached value
        interpreter._gpu_available = False
        result = interpreter._check_gpu_available()
        
        assert result is False, "Should return cached GPU unavailability"

    @given(vram_requirements)
    @settings(max_examples=50)
    def test_force_recheck_ignores_cache(self, vram_mb: int):
        """
        For any VRAM requirement, force_recheck should ignore cached value.
        """
        interpreter = GPURequiringInterpreter(vram_mb=vram_mb)
        
        # Set cached value to True
        interpreter._gpu_available = True
        
        # Mock torch to return False
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        
        with patch.dict('sys.modules', {'torch': mock_torch}):
            result = interpreter._check_gpu_available(force_recheck=True)
        
        assert result is False, "force_recheck should ignore cached value"


class TestGPUFallbackIntegration:
    """
    Integration tests for GPU fallback behavior.
    """

    @pytest.mark.asyncio
    async def test_call_vlm_falls_back_to_cloud_when_no_gpu(self):
        """
        When GPU is not available, _call_vlm should use cloud VLM.
        """
        interpreter = GPURequiringInterpreter(vram_mb=4096)
        interpreter._gpu_available = False  # Simulate no GPU
        
        # Mock the cloud VLM call
        mock_response = "Cloud VLM response"
        
        with patch.object(interpreter, '_call_cloud_vlm', new_callable=AsyncMock) as mock_cloud:
            mock_cloud.return_value = mock_response
            
            # Mock budget check to pass
            with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_budget:
                mock_budget.return_value = (True, 100.0)
                
                result = await interpreter._call_vlm(b"image_data", "test prompt")
        
        assert result == mock_response
        mock_cloud.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_vlm_tries_local_first_when_gpu_available(self):
        """
        When GPU is available, _call_vlm should try local VLM first.
        """
        interpreter = GPURequiringInterpreter(vram_mb=4096)
        interpreter._gpu_available = True  # Simulate GPU available
        
        # Mock the local VLM call to succeed
        mock_response = "Local VLM response"
        
        with patch.object(interpreter, '_call_local_vlm', new_callable=AsyncMock) as mock_local:
            mock_local.return_value = mock_response
            
            # Mock budget check to pass
            with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_budget:
                mock_budget.return_value = (True, 100.0)
                
                result = await interpreter._call_vlm(b"image_data", "test prompt")
        
        assert result == mock_response
        mock_local.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_vlm_falls_back_when_local_fails(self):
        """
        When local VLM fails, _call_vlm should fall back to cloud VLM.
        """
        interpreter = GPURequiringInterpreter(vram_mb=4096)
        interpreter._gpu_available = True  # Simulate GPU available
        
        # Mock the local VLM call to fail
        mock_cloud_response = "Cloud VLM response"
        
        with patch.object(interpreter, '_call_local_vlm', new_callable=AsyncMock) as mock_local:
            mock_local.side_effect = Exception("Local VLM failed")
            
            with patch.object(interpreter, '_call_cloud_vlm', new_callable=AsyncMock) as mock_cloud:
                mock_cloud.return_value = mock_cloud_response
                
                # Mock budget check to pass
                with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_budget:
                    mock_budget.return_value = (True, 100.0)
                    
                    result = await interpreter._call_vlm(b"image_data", "test prompt")
        
        assert result == mock_cloud_response
        mock_local.assert_called_once()
        mock_cloud.assert_called_once()

    @pytest.mark.asyncio
    async def test_explicit_provider_bypasses_local_gpu(self):
        """
        When provider is explicitly specified, should use cloud VLM directly.
        """
        interpreter = GPURequiringInterpreter(vram_mb=4096)
        interpreter._gpu_available = True  # Simulate GPU available
        
        mock_response = "Cloud VLM response"
        
        with patch.object(interpreter, '_call_local_vlm', new_callable=AsyncMock) as mock_local:
            with patch.object(interpreter, '_call_cloud_vlm', new_callable=AsyncMock) as mock_cloud:
                mock_cloud.return_value = mock_response
                
                # Mock budget check to pass
                with patch.object(interpreter, '_check_budget_before_call', new_callable=AsyncMock) as mock_budget:
                    mock_budget.return_value = (True, 100.0)
                    
                    result = await interpreter._call_vlm(
                        b"image_data", 
                        "test prompt",
                        provider="dashscope"  # Explicit provider
                    )
        
        assert result == mock_response
        mock_local.assert_not_called()  # Should not try local
        mock_cloud.assert_called_once()
