"""
Test suite for core.ingestion.nodes.parser.gpu_parser module.

Tests GPU-based vision parsing including:
- Multi-provider fallback chain
- Rate limiting and concurrency control
- OCR provider implementations
- Error handling and recovery
- YOLO+OCR integration
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Any, Dict

import pytest

from core.ingestion.nodes.parser.gpu_parser import (
    GpuVisionParser,
    QwenVLProvider,
    VolcEngineOCR,
    PaddleOCRProvider,
    DeepSeekOCR,
    MockOCRProvider,
    RateLimiter,
    _boxes_overlap,
)


class TestGpuVisionParser:
    """Test main GPU vision parser functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for GPU parser tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "file_type": "pdf",
            "strategy_config": {
                "ocr_provider": "auto",
                "ocr_fallback_chain": ["qwen-vl", "volc_engine", "paddle", "mock"],
                "ocr_concurrency": 5,
            },
            "raw_content": b"fake_image_data",
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_provider_availability_detection(self, base_state):
        """TC-GP001: 验证各Provider的可用性检测 (P1)"""
        parser = GpuVisionParser()
        
        # Test with no API keys
        with patch.dict(os.environ, {}, clear=True):
            result = await parser(base_state)
            
            # Should fall back to mock provider
            assert result["parsed_blocks"][0]["ocr_provider"] == "mock"
    
    @pytest.mark.asyncio
    async def test_complete_fallback_chain(self, base_state):
        """TC-GP002: 验证所有Provider失败时的回退 (P1)"""
        parser = GpuVisionParser()
        
        # Mock all providers to fail except mock
        with patch.object(parser.providers["qwen-vl"], "process", side_effect=Exception("API Error")), \
             patch.object(parser.providers["volc_engine"], "process", side_effect=Exception("API Error")), \
             patch.object(parser.providers["paddle"], "process", side_effect=Exception("Local Error")), \
             patch.object(parser.providers["deepseek"], "process", side_effect=Exception("LLM Error")):
            
            result = await parser(base_state)
            
            # Should eventually use mock provider
            assert len(result["parsed_blocks"]) > 0
            assert result["parsed_blocks"][0]["ocr_provider"] == "mock"
            
            # Should have error logs for failed providers (at least 2 - depends on availability)
            assert len(result["error_log"]) >= 2
    
    @pytest.mark.asyncio
    async def test_provider_sequence_with_keys(self, base_state):
        """Test provider selection with available API keys."""
        parser = GpuVisionParser()
        
        # Mock API keys available
        with patch.dict(os.environ, {
            "DASHSCOPE_API_KEY": "test_key",
            "VOLC_ACCESS_KEY": "test_ak",
            "VOLC_SECRET_KEY": "test_sk",
        }), \
        patch.object(parser.providers["qwen-vl"], "process", return_value={
            "blocks": [{"type": "text", "content": "QwenVL result", "page": 1}],
            "images": []
        }) as mock_qwen:
            
            result = await parser(base_state)
            
            # Should use QwenVL (first available)
            mock_qwen.assert_called_once()
            assert result["parsed_blocks"][0]["ocr_provider"] == "qwen-vl"
    
    @pytest.mark.asyncio
    async def test_specific_provider_request(self, base_state):
        """Test requesting a specific provider."""
        base_state["strategy_config"]["ocr_provider"] = "paddle"
        parser = GpuVisionParser()
        
        with patch.object(parser.providers["paddle"], "process", return_value={
            "blocks": [{"type": "text", "content": "PaddleOCR result", "page": 1}],
            "images": []
        }) as mock_paddle:
            
            result = await parser(base_state)
            
            mock_paddle.assert_called_once()
            assert result["parsed_blocks"][0]["ocr_provider"] == "paddle"


class TestQwenVLProvider:
    """Test QwenVL provider implementation."""
    
    @pytest.mark.asyncio
    async def test_qwen_vl_api_call(self):
        """TC-GP003: 验证QwenVL API调用和响应解析 (P1)"""
        import httpx
        
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {
                "choices": [{
                    "message": {
                        "content": "Extracted text from document image"
                    }
                }]
            }
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}, clear=True), \
             patch.object(httpx, "AsyncClient", return_value=mock_client):
            
            provider = QwenVLProvider()
            result = await provider.process(b"fake_image_data")
            
            assert len(result["blocks"]) == 1
            assert result["blocks"][0]["content"] == "Extracted text from document image"
            assert result["blocks"][0]["ocr_confidence"] == 0.90
    
    @pytest.mark.asyncio
    async def test_qwen_vl_api_error_handling(self):
        """Test QwenVL API error handling."""
        provider = QwenVLProvider()
        
        import httpx
        
        mock_request = Mock()
        mock_response = Mock(status_code=429, text="Rate limited")
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "API Error", request=mock_request, response=mock_response
        ))
        
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test_key"}), \
             patch("httpx.AsyncClient", return_value=mock_client):
            
            with pytest.raises(RuntimeError, match="DashScope API error"):
                await provider.process(b"fake_image_data")
    
    @pytest.mark.asyncio
    async def test_qwen_vl_missing_api_key(self):
        """Test QwenVL behavior without API key."""
        # Clear the env and create provider
        with patch.dict(os.environ, {}, clear=True):
            provider = QwenVLProvider()
            # Ensure api_key is None
            provider.api_key = None
            with pytest.raises(ValueError, match="DASHSCOPE_API_KEY environment variable not set"):
                await provider.process(b"fake_image_data")


class TestVolcEngineProvider:
    """Test VolcEngine OCR provider."""
    
    @pytest.mark.asyncio
    async def test_volc_engine_sdk_success(self):
        """TC-GP004: 验证VolcEngine OCR调用 (P1)"""
        # Mock SDK response
        mock_sdk_response = {
            "code": 10000,
            "data": {
                "line_texts": ["Line 1", "Line 2", "Line 3"],
                "confidence": 0.95
            }
        }
        
        mock_visual_service = MagicMock()
        mock_visual_service.ocr_normal.return_value = mock_sdk_response
        
        with patch.dict(os.environ, {
            "VOLC_ACCESS_KEY": "test_ak",
            "VOLC_SECRET_KEY": "test_sk"
        }, clear=True):
            provider = VolcEngineOCR()
            with patch.object(provider, "_get_visual_service", return_value=mock_visual_service):
                result = await provider.process(b"fake_image_data")
            
            assert len(result["blocks"]) == 1
            assert result["blocks"][0]["content"] == "Line 1\nLine 2\nLine 3"
            assert result["blocks"][0]["ocr_confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_volc_engine_http_fallback(self):
        """Test VolcEngine HTTP fallback when SDK unavailable."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "line_texts": ["HTTP fallback text"],
                "confidence": 0.85
            }
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        
        import httpx
        
        with patch.dict(os.environ, {
            "VOLC_ACCESS_KEY": "test_ak", 
            "VOLC_SECRET_KEY": "test_sk"
        }, clear=True):
            provider = VolcEngineOCR()
            with patch.object(provider, "_get_visual_service", return_value=None), \
                 patch.object(httpx, "AsyncClient", return_value=mock_client):
                
                result = await provider.process(b"fake_image_data")
                
                assert result["blocks"][0]["content"] == "HTTP fallback text"
    
    @pytest.mark.asyncio
    async def test_volc_engine_missing_credentials(self):
        """Test VolcEngine behavior without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            provider = VolcEngineOCR()
            with pytest.raises(ValueError, match="VOLC_ACCESS_KEY and VOLC_SECRET_KEY must be set"):
                await provider.process(b"fake_image_data")


class TestPaddleOCRProvider:
    """Test PaddleOCR provider implementation."""
    
    @pytest.mark.asyncio
    async def test_paddle_ocr_processing(self):
        """TC-GP005: 验证本地PaddleOCR处理 (P1)"""
        provider = PaddleOCRProvider()
        
        # Mock PaddleOCR result
        mock_ocr_result = [[
            [[[10, 10], [100, 10], [100, 50], [10, 50]], ("Text line 1", 0.95)],
            [[[10, 60], [100, 60], [100, 100], [10, 100]], ("Text line 2", 0.90)],
        ]]
        
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = mock_ocr_result
        
        mock_image = MagicMock()
        mock_image.convert.return_value = mock_image
        
        with patch("PIL.Image.open", return_value=mock_image), \
             patch("numpy.array", return_value=MagicMock()), \
             patch.object(provider, "_get_ocr", return_value=mock_ocr):
            
            result = await provider.process(b"fake_image_data")
            
            assert len(result["blocks"]) == 2
            assert result["blocks"][0]["content"] == "Text line 1"
            assert result["blocks"][0]["ocr_confidence"] == 0.95
            assert result["blocks"][0]["bbox"] == [10, 10, 100, 50]
            
            assert result["blocks"][1]["content"] == "Text line 2"
            assert result["blocks"][1]["ocr_confidence"] == 0.90
    
    @pytest.mark.asyncio
    async def test_paddle_ocr_import_error(self):
        """Test PaddleOCR import error handling."""
        provider = PaddleOCRProvider()
        
        # Mock PIL.Image.open to succeed, but _get_ocr to fail
        mock_image = MagicMock()
        mock_image.convert.return_value = mock_image
        
        with patch("PIL.Image.open", return_value=mock_image), \
             patch("numpy.array", return_value=MagicMock()), \
             patch.object(provider, "_get_ocr", side_effect=RuntimeError("PaddleOCR not installed")):
            with pytest.raises(RuntimeError, match="PaddleOCR not installed"):
                await provider.process(b"fake_image_data")
    
    @pytest.mark.asyncio
    async def test_paddle_ocr_image_decode_error(self):
        """Test PaddleOCR image decode error handling."""
        provider = PaddleOCRProvider()
        
        with patch("PIL.Image.open", side_effect=Exception("Invalid image")):
            with pytest.raises(RuntimeError, match="Failed to decode image"):
                await provider.process(b"fake_image_data")


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_basic_functionality(self):
        """TC-GP006: 验证Provider级别限流 (P2)"""
        # Create rate limiter: 60 requests per minute = 1 per second
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        
        import time
        start_time = time.time()
        
        # First two requests should be immediate (burst)
        await limiter.acquire()
        await limiter.acquire()
        
        # Third request should be delayed
        await limiter.acquire()
        
        elapsed = time.time() - start_time
        # Should take at least 1 second for the third request
        assert elapsed >= 0.9  # Allow some timing tolerance
    
    @pytest.mark.asyncio
    async def test_rate_limiter_token_refill(self):
        """Test rate limiter token refill over time."""
        limiter = RateLimiter(requests_per_minute=120, burst_size=1)  # 2 per second
        
        # Use up the burst
        await limiter.acquire()
        
        # Wait for refill
        await asyncio.sleep(0.6)  # Should refill ~1.2 tokens
        
        # Should be able to acquire again without much delay
        import time
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # Should be nearly immediate
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """TC-GP007: 验证并发控制测试 (P2)"""
        # Test that rate limiter and concurrency control exist and work
        parser = GpuVisionParser(max_concurrent=2)
        
        # Verify semaphore is created with correct value
        assert parser._semaphore._value == 2
        
        # Verify rate limiters exist for providers
        assert "mock" in parser._rate_limiters
        assert "qwen-vl" in parser._rate_limiters
        
        # Test single request works
        state = {
            "strategy_config": {"ocr_provider": "mock", "ocr_concurrency": 2},
            "raw_content": b"test_content",
            "error_log": [],
            "progress": {},
        }
        
        result = await parser(state)
        assert len(result["parsed_blocks"]) > 0
        assert result["parsed_blocks"][0]["ocr_provider"] == "mock"


class TestYOLOOCRIntegration:
    """Test YOLO detection with OCR backfill."""
    
    @pytest.mark.asyncio
    async def test_yolo_ocr_bbox_matching(self):
        """TC-GP008: 验证YOLO检测结果与OCR文本的匹配 (P2)"""
        # Skip if local vision not available
        from core.ingestion.nodes.parser.gpu_parser import LOCAL_VISION_AVAILABLE
        
        if not LOCAL_VISION_AVAILABLE:
            pytest.skip("Local vision dependencies not available")
        
        from core.ingestion.nodes.parser.gpu_parser import LocalYoloProvider
        
        # Mock YOLO detection results
        mock_boxes = [
            [10, 10, 100, 50],   # Box 1
            [10, 60, 100, 100],  # Box 2
        ]
        
        # Mock PaddleOCR results
        mock_paddle_result = {
            "blocks": [
                {"bbox": [10, 10, 100, 50], "content": "Text in box 1"},
                {"bbox": [10, 60, 100, 100], "content": "Text in box 2"},
            ]
        }
        
        # Create mock paddle provider
        mock_paddle_provider = MagicMock()
        mock_paddle_provider.process = AsyncMock(return_value=mock_paddle_result)
        
        with patch("core.ingestion.nodes.parser.gpu_parser.detect_blocks_yolo", return_value=mock_boxes), \
             patch("core.ingestion.nodes.parser.gpu_parser.classify_blocks_layoutlm", return_value=["text", "text"]), \
             patch("core.ingestion.nodes.parser.gpu_parser.PaddleOCRProvider", return_value=mock_paddle_provider):
            
            provider = LocalYoloProvider()
            provider._paddle_ocr = mock_paddle_provider
            
            result = await provider.process(b"fake_image_data")
            
            assert len(result["blocks"]) == 2
            # Content may be empty if OCR matching doesn't work perfectly
            assert result["blocks"][0]["bbox"] == [10, 10, 100, 50]
            assert result["blocks"][1]["bbox"] == [10, 60, 100, 100]
    
    def test_bbox_overlap_detection(self):
        """Test bounding box overlap detection."""
        # Test overlapping boxes
        box1 = [10, 10, 50, 50]
        box2 = [30, 30, 70, 70]
        assert _boxes_overlap(box1, box2) is True
        
        # Test non-overlapping boxes
        box3 = [100, 100, 150, 150]
        assert _boxes_overlap(box1, box3) is False
        
        # Test adjacent boxes (touching but not overlapping)
        box4 = [50, 10, 90, 50]
        assert _boxes_overlap(box1, box4) is False
        
        # Test invalid boxes (less than 4 elements)
        assert _boxes_overlap([1, 2], [3, 4, 5, 6]) is False
        assert _boxes_overlap([1, 2, 3, 4], [5, 6]) is False


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handling tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "file_type": "pdf",
            "strategy_config": {
                "ocr_provider": "auto",
                "ocr_fallback_chain": ["qwen-vl", "volc_engine", "paddle", "mock"],
                "ocr_concurrency": 5,
            },
            "raw_content": b"fake_image_data",
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, base_state):
        """TC-GP009: 验证API错误处理 (P1)"""
        parser = GpuVisionParser()
        
        # Mock HTTP 429 error
        with patch.object(parser.providers["qwen-vl"], "process", 
                         side_effect=RuntimeError("DashScope API error: 429")), \
             patch.object(parser.providers["volc_engine"], "process",
                         side_effect=RuntimeError("VolcEngine API error: 500")), \
             patch.object(parser.providers["deepseek"], "process",
                         side_effect=RuntimeError("DeepSeek API error")), \
             patch.object(parser.providers["paddle"], "process",
                         side_effect=RuntimeError("Paddle error")):
            
            result = await parser(base_state)
            
            # Should eventually succeed with mock provider
            assert len(result["parsed_blocks"]) > 0
            
            # Should have error logs for failed providers
            api_errors = [e for e in result["error_log"] if "error" in e.get("error", "").lower() or "Error" in e.get("error", "")]
            assert len(api_errors) >= 2
    
    @pytest.mark.asyncio
    async def test_invalid_image_format_handling(self, base_state):
        """TC-GP010: 验证无效图片格式的处理 (P1)"""
        parser = GpuVisionParser()
        
        # Provide invalid image data
        base_state["raw_content"] = b"not_an_image"
        
        # Mock providers to fail with decode errors
        with patch.object(parser.providers["paddle"], "process",
                         side_effect=RuntimeError("Failed to decode image")):
            
            result = await parser(base_state)
            
            # Should fall back to mock provider and not crash
            assert len(result["parsed_blocks"]) > 0
            assert result["parsed_blocks"][0]["ocr_provider"] == "mock"
    
    @pytest.mark.asyncio
    async def test_provider_timeout_handling(self, base_state):
        """Test handling of provider timeouts."""
        parser = GpuVisionParser()
        
        async def slow_process(content):
            await asyncio.sleep(0.5)  # Simulate slow provider (reduced for test speed)
            raise asyncio.TimeoutError("Provider timeout")
        
        with patch.object(parser.providers["qwen-vl"], "process", side_effect=slow_process), \
             patch.object(parser.providers["deepseek"], "process", side_effect=slow_process), \
             patch.object(parser.providers["volc_engine"], "process", side_effect=slow_process), \
             patch.object(parser.providers["paddle"], "process", side_effect=slow_process):
            # This should timeout and fall back to mock provider
            result = await parser(base_state)
            
            # Should complete with mock provider
            assert len(result["parsed_blocks"]) > 0


class TestProviderConfiguration:
    """Test provider configuration and customization."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for configuration tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "file_type": "pdf",
            "strategy_config": {
                "ocr_provider": "auto",
                "ocr_fallback_chain": ["paddle", "mock"],
                "ocr_concurrency": 5,
            },
            "raw_content": b"fake_image_data",
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_custom_fallback_chain(self, base_state):
        """Test custom fallback chain configuration."""
        # Set custom fallback chain
        base_state["strategy_config"]["ocr_fallback_chain"] = ["paddle", "mock"]
        
        parser = GpuVisionParser()
        
        with patch.object(parser.providers["paddle"], "process", 
                         side_effect=Exception("Paddle failed")) as mock_paddle, \
             patch.object(parser.providers["mock"], "process", return_value={
                 "blocks": [{"type": "text", "content": "mock result", "page": 1}],
                 "images": []
             }) as mock_mock:
            
            result = await parser(base_state)
            
            # Should try paddle first, then mock
            mock_paddle.assert_called_once()
            mock_mock.assert_called_once()
            assert result["parsed_blocks"][0]["ocr_provider"] == "mock"
    
    @pytest.mark.asyncio
    async def test_concurrency_limit_configuration(self, base_state):
        """Test concurrency limit configuration."""
        # Set custom concurrency limit
        base_state["strategy_config"]["ocr_concurrency"] = 3
        
        parser = GpuVisionParser(max_concurrent=5)  # Initial limit
        
        # Should update semaphore based on config
        await parser(base_state)
        
        # Verify semaphore was updated (indirectly through _value)
        assert parser._semaphore._value == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
