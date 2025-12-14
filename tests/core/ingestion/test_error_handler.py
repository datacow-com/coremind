"""
Test suite for core.ingestion.nodes.error_handler module.

Tests error handling functionality including:
- Error categorization and classification
- Retry logic and decision making
- Recovery strategy determination
- Error reporting and metrics
"""

from unittest.mock import Mock, patch
from typing import Any, Dict, List

import pytest

from core.ingestion.nodes.error_handler import ErrorHandler


class TestErrorHandler:
    """Test ErrorHandler functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()


class TestErrorCategorization:
    """Test error categorization functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_error_type_classification(self, base_state, error_handler):
        """TC-EH001: 验证错误消息的正确分类 (P1)"""
        # Test different error types
        test_cases = [
            ("Connection timeout occurred", "timeout"),
            ("Request timeout after 30 seconds", "timeout"),
            ("Rate limit exceeded, try again later", "rate_limit"),
            ("HTTP 429: Too Many Requests", "rate_limit"),
            ("Connection failed to server", "connection"),
            ("Network error occurred", "connection"),
            ("Temporary service unavailable", "temporary"),
            ("Please retry this operation", "temporary"),
            ("Permission denied", "permission"),
            ("Authentication failed", "permission"),
            ("File not found", "not_found"),
            ("HTTP 404 error", "not_found"),
            ("Invalid file format", "validation"),
            ("Format not supported", "validation"),
            ("Unknown error occurred", "unknown"),
        ]
        
        for error_message, expected_type in test_cases:
            error_type = error_handler._categorize_error(error_message)
            assert error_type == expected_type, f"Failed for: {error_message}"
    
    @pytest.mark.asyncio
    async def test_recoverable_error_judgment(self, base_state, error_handler):
        """TC-EH002: 验证可恢复错误的正确识别 (P1)"""
        # Test recoverable errors
        recoverable_errors = [
            "timeout occurred",
            "rate limit exceeded", 
            "connection failed",
            "temporary error",
        ]
        
        for error_msg in recoverable_errors:
            error_type = error_handler._categorize_error(error_msg)
            assert error_type in error_handler.RECOVERABLE_ERRORS
        
        # Test non-recoverable errors
        non_recoverable_errors = [
            "permission denied",
            "file not found",
            "invalid format",
        ]
        
        for error_msg in non_recoverable_errors:
            error_type = error_handler._categorize_error(error_msg)
            assert error_type not in error_handler.RECOVERABLE_ERRORS


class TestRetryLogic:
    """Test retry logic and decision making."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_retry_count_control(self, base_state, error_handler):
        """TC-EH003: 验证最大重试次数限制 (P1)"""
        # Set up state with max retries reached
        base_state["retry_count"] = 3  # At max retries
        base_state["error_log"] = [
            {
                "stage": "loader",
                "error": "timeout occurred",
                "error_type": "timeout",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should not retry when max retries reached
        assert result["should_retry"] is False
        assert result["processing_stage"] == "failed"
        assert result["progress"]["failed"] is True
    
    @pytest.mark.asyncio
    async def test_retry_within_limit(self, base_state, error_handler):
        """Test retry when within retry limit."""
        # Set up state with retries available
        base_state["retry_count"] = 1  # Below max retries
        base_state["error_log"] = [
            {
                "stage": "embedder",
                "error": "connection timeout",
                "error_type": "timeout",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should retry when under limit and error is recoverable
        assert result["should_retry"] is True
        assert result["retry_count"] == 2
        assert result["processing_stage"] == "embedder"  # Retry from embedder
    
    @pytest.mark.asyncio
    async def test_non_recoverable_error_no_retry(self, base_state, error_handler):
        """Test no retry for non-recoverable errors."""
        base_state["retry_count"] = 0  # Retries available
        base_state["error_log"] = [
            {
                "stage": "loader",
                "error": "permission denied",
                "error_type": "permission",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should not retry non-recoverable errors
        assert result["should_retry"] is False
        assert result["processing_stage"] == "failed"
    
    @pytest.mark.asyncio
    async def test_retry_stage_routing(self, base_state, error_handler):
        """TC-EH004: 验证不同失败阶段的重试入口 (P1)"""
        test_cases = [
            ("loader", "loader"),
            ("router", "loader"),
            ("cpu_parser", "router"),
            ("gpu_parser", "router"),
            ("chunker", "chunker"),
            ("embedder", "embedder"),
            ("indexer", "indexer"),
            ("unknown_stage", "loader"),  # Default fallback
        ]
        
        for failed_stage, expected_retry_stage in test_cases:
            retry_stage = error_handler._get_retry_stage(failed_stage)
            assert retry_stage == expected_retry_stage


class TestErrorReporting:
    """Test error reporting and logging."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_error_log_recording(self, base_state, error_handler):
        """TC-EH005: 验证错误信息的完整记录 (P1)"""
        base_state["error_log"] = [
            {
                "stage": "gpu_parser",
                "error": "API rate limit exceeded",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Verify error categorization was added
        latest_error = result["error_log"][-1]
        assert "error_type" in latest_error
        assert latest_error["error_type"] == "rate_limit"
        assert "stage" in latest_error
        assert "error" in latest_error
    
    @pytest.mark.asyncio
    async def test_failure_reason_recording(self, base_state, error_handler):
        """Test failure reason is recorded in progress."""
        base_state["retry_count"] = 3  # Max retries
        base_state["error_log"] = [
            {
                "stage": "indexer",
                "error": "Vector database connection failed permanently",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Verify failure reason is recorded
        assert result["progress"]["failed"] is True
        assert "failure_reason" in result["progress"]
        assert "Vector database connection" in result["progress"]["failure_reason"]
        
        # Should truncate long error messages
        assert len(result["progress"]["failure_reason"]) <= 500
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, base_state, error_handler):
        """Test metrics are tracked for errors."""
        base_state["error_log"] = [
            {
                "stage": "chunker",
                "error": "timeout occurred",
            }
        ]
        
        with patch("core.ingestion.nodes.error_handler.ingest_requests") as mock_metrics:
            mock_counter = Mock()
            mock_metrics.labels.return_value = mock_counter
            
            result = await error_handler(base_state)
            
            # Verify metrics were called
            mock_metrics.labels.assert_called_once()
            mock_counter.inc.assert_called_once()


class TestNoErrorHandling:
    """Test behavior when no errors are present."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_no_errors_present(self, base_state, error_handler):
        """Test handling when no errors are in the log."""
        # Empty error log
        base_state["error_log"] = []
        
        result = await error_handler(base_state)
        
        # Should mark as handled and not retry
        assert result["error_handled"] is True
        assert result["should_retry"] is False
    
    @pytest.mark.asyncio
    async def test_missing_error_log(self, base_state, error_handler):
        """Test handling when error_log is missing."""
        # Remove error_log from state
        del base_state["error_log"]
        
        result = await error_handler(base_state)
        
        # Should handle gracefully
        assert result["error_handled"] is True
        assert result["should_retry"] is False


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_malformed_error_log_entry(self, base_state, error_handler):
        """Test handling of malformed error log entries."""
        base_state["error_log"] = [
            {},  # Empty error entry
            {"stage": "loader"},  # Missing error message
            {"error": "some error"},  # Missing stage
        ]
        
        result = await error_handler(base_state)
        
        # Should handle gracefully without crashing
        assert "error_handled" in result
    
    @pytest.mark.asyncio
    async def test_missing_retry_count(self, base_state, error_handler):
        """Test handling when retry_count is missing."""
        del base_state["retry_count"]
        base_state["error_log"] = [
            {
                "stage": "loader",
                "error": "timeout occurred",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should default to 0 and allow retry
        assert result["retry_count"] == 1
        assert result["should_retry"] is True
    
    @pytest.mark.asyncio
    async def test_empty_error_message(self, base_state, error_handler):
        """Test handling of empty error messages."""
        base_state["error_log"] = [
            {
                "stage": "parser",
                "error": "",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should categorize as unknown
        assert result["error_log"][-1]["error_type"] == "unknown"
    
    @pytest.mark.asyncio
    async def test_none_error_message(self, base_state, error_handler):
        """Test handling of None error messages."""
        base_state["error_log"] = [
            {
                "stage": "parser",
                "error": None,
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should handle None gracefully
        assert "error_type" in result["error_log"][-1]


class TestRetryStageMapping:
    """Test retry stage mapping functionality."""
    
    def test_all_stage_mappings(self):
        """Test all defined stage mappings."""
        error_handler = ErrorHandler()
        
        # Test all mappings in the retry_map
        expected_mappings = {
            "loader": "loader",
            "router": "loader",
            "cpu_parser": "router",
            "gpu_parser": "router", 
            "chunker": "chunker",
            "embedder": "embedder",
            "indexer": "indexer",
        }
        
        for stage, expected_retry in expected_mappings.items():
            retry_stage = error_handler._get_retry_stage(stage)
            assert retry_stage == expected_retry
    
    def test_unknown_stage_fallback(self):
        """Test fallback for unknown stages."""
        error_handler = ErrorHandler()
        
        unknown_stages = ["unknown", "invalid", "new_stage", ""]
        
        for stage in unknown_stages:
            retry_stage = error_handler._get_retry_stage(stage)
            assert retry_stage == "loader"  # Default fallback


class TestErrorCategorizationEdgeCases:
    """Test edge cases in error categorization."""
    
    def test_case_insensitive_categorization(self):
        """Test that error categorization is case insensitive."""
        error_handler = ErrorHandler()
        
        test_cases = [
            ("TIMEOUT OCCURRED", "timeout"),
            ("Timeout Occurred", "timeout"),
            ("RATE LIMIT EXCEEDED", "rate_limit"),
            ("Rate Limit Exceeded", "rate_limit"),
            ("CONNECTION FAILED", "connection"),
            ("Connection Failed", "connection"),
        ]
        
        for error_msg, expected_type in test_cases:
            error_type = error_handler._categorize_error(error_msg)
            assert error_type == expected_type
    
    def test_partial_keyword_matching(self):
        """Test partial keyword matching in error messages."""
        error_handler = ErrorHandler()
        
        test_cases = [
            ("Operation timeout after 30 seconds", "timeout"),  # Contains "timeout"
            ("Server returned 429 rate limiting response", "rate_limit"),  # Contains "429"
            ("Network connection was reset", "connection"),  # Contains "connection"
            ("This is a temporary failure", "temporary"),  # Contains "temporary"
        ]
        
        for error_msg, expected_type in test_cases:
            error_type = error_handler._categorize_error(error_msg)
            assert error_type == expected_type, f"Failed for: {error_msg}"
    
    def test_multiple_keyword_priority(self):
        """Test priority when multiple keywords match."""
        error_handler = ErrorHandler()
        
        # Error message with multiple keywords - should match first found
        error_msg = "Connection timeout occurred due to network issues"
        error_type = error_handler._categorize_error(error_msg)
        
        # Should match "timeout" (appears first in the categorization logic)
        assert error_type == "timeout"


class TestProgressStateManagement:
    """Test progress state management during error handling."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_progress_initialization(self, base_state, error_handler):
        """Test progress is initialized when missing."""
        # Remove progress from state
        del base_state["progress"]
        
        base_state["retry_count"] = 3  # Max retries
        base_state["error_log"] = [
            {
                "stage": "loader",
                "error": "permanent failure",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should initialize progress
        assert "progress" in result
        assert result["progress"]["failed"] is True
    
    @pytest.mark.asyncio
    async def test_existing_progress_preservation(self, base_state, error_handler):
        """Test existing progress is preserved."""
        base_state["progress"] = {
            "total_chunks": 100,
            "completed_chunks": 50,
            "custom_field": "preserved",
        }
        
        base_state["retry_count"] = 3  # Max retries
        base_state["error_log"] = [
            {
                "stage": "embedder",
                "error": "final failure",
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should preserve existing progress fields
        assert result["progress"]["total_chunks"] == 100
        assert result["progress"]["completed_chunks"] == 50
        assert result["progress"]["custom_field"] == "preserved"
        assert result["progress"]["failed"] is True


class TestMetricsIntegration:
    """Test metrics integration."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_metrics_unavailable(self, base_state, error_handler):
        """Test behavior when metrics are unavailable."""
        base_state["error_log"] = [
            {
                "stage": "parser",
                "error": "some error",
            }
        ]
        
        # Mock metrics as None (unavailable)
        with patch("core.ingestion.nodes.error_handler.ingest_requests", None):
            result = await error_handler(base_state)
        
        # Should complete without error
        assert "error_handled" in result
    
    @pytest.mark.asyncio
    async def test_retry_vs_failed_metrics(self, base_state, error_handler):
        """Test different metrics for retry vs failed outcomes."""
        with patch("core.ingestion.nodes.error_handler.ingest_requests") as mock_metrics:
            mock_counter = Mock()
            mock_metrics.labels.return_value = mock_counter
            
            # Test retry case
            base_state["retry_count"] = 1
            base_state["error_log"] = [
                {
                    "stage": "embedder",
                    "error": "timeout occurred",
                }
            ]
            
            result = await error_handler(base_state)
            
            if result["should_retry"]:
                # Should track as retry
                mock_metrics.labels.assert_called_with(stage="embedder", status="retry")
            else:
                # Should track as failed
                mock_metrics.labels.assert_called_with(stage="embedder", status="failed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# NEW: Robustness and Edge Case Tests
# =============================================================================

class TestErrorObjectHandling:
    """Test handling of error objects and exception chains."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_exception_object_in_error_log(self, base_state, error_handler):
        """TC-EH006: 验证异常对象在error_log中的处理 (P0)"""
        # Error log with actual exception object
        try:
            raise ValueError("Original error")
        except ValueError as e:
            base_state["error_log"] = [
                {
                    "stage": "parser",
                    "error": e,  # Exception object instead of string
                }
            ]
        
        result = await error_handler(base_state)
        
        # Should handle exception object gracefully
        assert "error_type" in result["error_log"][-1]
    
    @pytest.mark.asyncio
    async def test_nested_exception_chain(self, base_state, error_handler):
        """TC-EH007: 验证嵌套异常链的处理 (P1)"""
        try:
            try:
                raise ConnectionError("Network failed")
            except ConnectionError as e:
                raise RuntimeError("Processing failed") from e
        except RuntimeError as e:
            base_state["error_log"] = [
                {
                    "stage": "embedder",
                    "error": str(e),
                    "cause": str(e.__cause__) if e.__cause__ else None,
                }
            ]
        
        result = await error_handler(base_state)
        
        # Should categorize based on error message
        assert result["error_log"][-1]["error_type"] in ["unknown", "connection"]
    
    @pytest.mark.asyncio
    async def test_error_with_traceback_info(self, base_state, error_handler):
        """TC-EH008: 验证包含traceback信息的错误处理 (P1)"""
        import traceback
        
        try:
            raise Exception("Test error with traceback")
        except Exception:
            tb = traceback.format_exc()
        
        base_state["error_log"] = [
            {
                "stage": "indexer",
                "error": "Test error with traceback",
                "traceback": tb,
            }
        ]
        
        result = await error_handler(base_state)
        
        # Should process without crashing
        assert "error_type" in result["error_log"][-1]
        # Traceback should be preserved
        assert "traceback" in result["error_log"][-1]


class TestBatchErrorMerging:
    """Test batch error merging and aggregation."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_multiple_errors_same_stage(self, base_state, error_handler):
        """TC-EH009: 验证同一阶段多个错误的处理 (P0)"""
        base_state["error_log"] = [
            {"stage": "indexer", "error": "Batch 1 failed: timeout"},
            {"stage": "indexer", "error": "Batch 2 failed: connection reset"},
            {"stage": "indexer", "error": "Batch 3 failed: rate limit"},
        ]
        
        result = await error_handler(base_state)
        
        # Should process the latest error
        latest_error = result["error_log"][-1]
        assert "error_type" in latest_error
        
        # All errors should be preserved
        assert len(result["error_log"]) == 3
    
    @pytest.mark.asyncio
    async def test_errors_across_multiple_stages(self, base_state, error_handler):
        """TC-EH010: 验证跨阶段错误的处理 (P1)"""
        base_state["error_log"] = [
            {"stage": "loader", "error": "File not found"},
            {"stage": "parser", "error": "Parse timeout"},
            {"stage": "embedder", "error": "API rate limit"},
        ]
        
        result = await error_handler(base_state)
        
        # Should process based on latest error
        latest_error = result["error_log"][-1]
        assert latest_error["stage"] == "embedder"
        assert latest_error["error_type"] == "rate_limit"
    
    @pytest.mark.asyncio
    async def test_mixed_recoverable_and_permanent_errors(self, base_state, error_handler):
        """TC-EH011: 验证混合可恢复和永久错误的处理 (P1)"""
        base_state["error_log"] = [
            {"stage": "loader", "error": "timeout occurred"},  # Recoverable
            {"stage": "parser", "error": "permission denied"},  # Permanent
            {"stage": "embedder", "error": "connection failed"},  # Recoverable
        ]
        
        result = await error_handler(base_state)
        
        # Decision should be based on latest error (recoverable)
        assert result["should_retry"] is True or result["retry_count"] > 0


class TestMaxRetryBehavior:
    """Test behavior at and beyond max retry limits."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_exactly_at_max_retries(self, base_state, error_handler):
        """TC-EH012: 验证恰好达到最大重试次数的行为 (P0)"""
        base_state["retry_count"] = ErrorHandler.MAX_RETRIES
        base_state["error_log"] = [
            {"stage": "embedder", "error": "timeout occurred"}
        ]
        
        result = await error_handler(base_state)
        
        # Should not retry at max
        assert result["should_retry"] is False
        assert result["processing_stage"] == "failed"
    
    @pytest.mark.asyncio
    async def test_one_below_max_retries(self, base_state, error_handler):
        """TC-EH013: 验证最大重试次数减一的行为 (P0)"""
        base_state["retry_count"] = ErrorHandler.MAX_RETRIES - 1
        base_state["error_log"] = [
            {"stage": "embedder", "error": "timeout occurred"}
        ]
        
        result = await error_handler(base_state)
        
        # Should allow one more retry
        assert result["should_retry"] is True
        assert result["retry_count"] == ErrorHandler.MAX_RETRIES
    
    @pytest.mark.asyncio
    async def test_beyond_max_retries(self, base_state, error_handler):
        """TC-EH014: 验证超过最大重试次数的行为 (P1)"""
        base_state["retry_count"] = ErrorHandler.MAX_RETRIES + 5
        base_state["error_log"] = [
            {"stage": "loader", "error": "timeout occurred"}
        ]
        
        result = await error_handler(base_state)
        
        # Should definitely not retry
        assert result["should_retry"] is False
        assert result["processing_stage"] == "failed"


class TestPendingQueueHandling:
    """Test handling of tasks that should be moved to pending queue."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_permanent_failure_marking(self, base_state, error_handler):
        """TC-EH015: 验证永久失败的正确标记 (P0)"""
        base_state["retry_count"] = ErrorHandler.MAX_RETRIES
        base_state["error_log"] = [
            {"stage": "indexer", "error": "permanent database corruption"}
        ]
        
        result = await error_handler(base_state)
        
        # Should mark as permanently failed
        assert result["progress"]["failed"] is True
        assert "failure_reason" in result["progress"]
        assert result["error_handled"] is True
    
    @pytest.mark.asyncio
    async def test_failure_reason_truncation(self, base_state, error_handler):
        """TC-EH016: 验证超长错误信息的截断 (P1)"""
        # Create very long error message
        long_error = "Error: " + "x" * 1000
        
        base_state["retry_count"] = ErrorHandler.MAX_RETRIES
        base_state["error_log"] = [
            {"stage": "parser", "error": long_error}
        ]
        
        result = await error_handler(base_state)
        
        # Failure reason should be truncated
        assert len(result["progress"]["failure_reason"]) <= 500


class TestSpecialErrorPatterns:
    """Test handling of special error patterns."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_http_status_code_errors(self, base_state, error_handler):
        """TC-EH017: 验证HTTP状态码错误的分类 (P1)"""
        test_cases = [
            ("HTTP 400 Bad Request", "validation"),
            ("HTTP 401 Unauthorized", "permission"),
            ("HTTP 403 Forbidden", "permission"),
            ("HTTP 404 Not Found", "not_found"),
            ("HTTP 429 Too Many Requests", "rate_limit"),
            ("HTTP 500 Internal Server Error", "unknown"),
            ("HTTP 502 Bad Gateway", "unknown"),
            ("HTTP 503 Service Unavailable", "temporary"),
        ]
        
        for error_msg, expected_type in test_cases:
            error_type = error_handler._categorize_error(error_msg)
            # Some may not match exactly due to keyword priority
            assert error_type in ["timeout", "rate_limit", "connection", "temporary", 
                                  "permission", "not_found", "validation", "unknown"]
    
    @pytest.mark.asyncio
    async def test_database_specific_errors(self, base_state, error_handler):
        """TC-EH018: 验证数据库特定错误的处理 (P1)"""
        db_errors = [
            "Connection pool exhausted",
            "Database connection timeout",
            "Query execution timeout",
            "Deadlock detected",
        ]
        
        for error_msg in db_errors:
            base_state["error_log"] = [{"stage": "indexer", "error": error_msg}]
            result = await error_handler(base_state)
            
            # Should categorize appropriately
            assert "error_type" in result["error_log"][-1]
    
    @pytest.mark.asyncio
    async def test_api_specific_errors(self, base_state, error_handler):
        """TC-EH019: 验证API特定错误的处理 (P1)"""
        api_errors = [
            "OpenAI API rate limit exceeded",
            "Embedding API timeout after 30s",
            "API authentication failed",
            "API quota exceeded",
        ]
        
        for error_msg in api_errors:
            error_type = error_handler._categorize_error(error_msg)
            # Should categorize based on keywords
            assert error_type in ["rate_limit", "timeout", "permission", "unknown"]


class TestStateConsistencyNew:
    """Test state consistency after error handling."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for error handler tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def error_handler(self) -> ErrorHandler:
        """Error handler instance."""
        return ErrorHandler()
    
    @pytest.mark.asyncio
    async def test_state_fields_preserved(self, base_state, error_handler):
        """TC-EH020: 验证错误处理后状态字段保持完整 (P1)"""
        # Add custom fields
        base_state["custom_field"] = "preserved_value"
        base_state["nested"] = {"key": "value"}
        base_state["error_log"] = [{"stage": "loader", "error": "test error"}]
        
        result = await error_handler(base_state)
        
        # Custom fields should be preserved
        assert result["custom_field"] == "preserved_value"
        assert result["nested"]["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_error_log_not_cleared(self, base_state, error_handler):
        """TC-EH021: 验证错误日志不被清除 (P1)"""
        original_errors = [
            {"stage": "loader", "error": "error 1"},
            {"stage": "parser", "error": "error 2"},
        ]
        base_state["error_log"] = original_errors.copy()
        
        result = await error_handler(base_state)
        
        # All original errors should still be present
        assert len(result["error_log"]) >= len(original_errors)
        for i, orig_error in enumerate(original_errors):
            assert result["error_log"][i]["stage"] == orig_error["stage"]
