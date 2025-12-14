"""
Test suite for core.ingestion.nodes.finalizer module.

Tests finalization functionality including:
- Final status updates and metrics calculation
- Temporary file cleanup
- SSE progress notifications
- Error handling during cleanup
"""

import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict, List

import pytest

from core.ingestion.nodes.finalizer import Finalizer


class TestFinalizer:
    """Test Finalizer functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}"}
                for i in range(10)
            ],
            "error_log": [
                {"stage": "parser", "error": "Minor parsing warning"},
            ],
            "quality_metrics": {
                "original_count": 15,
                "removed_count": 5,
            },
            "progress": {
                "indexed_vector": 8,
                "indexed_keyword": 10,
            },
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()


class TestStatusUpdates:
    """Test final status updates and metrics."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}"}
                for i in range(10)
            ],
            "error_log": [
                {"stage": "parser", "error": "Minor parsing warning"},
            ],
            "quality_metrics": {
                "original_count": 15,
                "removed_count": 5,
            },
            "progress": {
                "indexed_vector": 8,
                "indexed_keyword": 10,
            },
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_final_status_setting(self, base_state, finalizer):
        """TC-F001: 验证处理完成后的状态更新 (P1)"""
        result = await finalizer(base_state)
        
        # Verify final status
        assert result["processing_stage"] == "completed"
        assert result["progress"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_metrics_statistics_accuracy(self, base_state, finalizer):
        """TC-F002: 验证最终指标的准确统计 (P2)"""
        result = await finalizer(base_state)
        
        progress = result["progress"]
        
        # Verify chunk statistics
        assert progress["total_chunks"] == 10
        assert progress["error_count"] == 1
        
        # Verify indexing statistics
        assert progress["indexed_vector"] == 8
        assert progress["indexed_keyword"] == 10
        
        # Verify quality statistics
        assert progress["quality_original"] == 15
        assert progress["quality_filtered"] == 5
    
    @pytest.mark.asyncio
    async def test_progress_initialization(self, base_state, finalizer):
        """Test progress initialization when missing."""
        # Remove progress from state
        del base_state["progress"]
        
        result = await finalizer(base_state)
        
        # Should initialize progress
        assert "progress" in result
        assert result["progress"]["status"] == "completed"
        assert result["progress"]["total_chunks"] == 10
    
    @pytest.mark.asyncio
    async def test_missing_quality_metrics(self, base_state, finalizer):
        """Test handling when quality metrics are missing."""
        del base_state["quality_metrics"]
        
        result = await finalizer(base_state)
        
        # Should handle gracefully
        progress = result["progress"]
        assert "quality_original" not in progress or progress["quality_original"] == 0
        assert "quality_filtered" not in progress or progress["quality_filtered"] == 0


class TestTemporaryFileCleanup:
    """Test temporary file cleanup functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}"}
                for i in range(10)
            ],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, base_state, finalizer):
        """TC-F003: 验证临时文件的正确清理 (P1)"""
        # Create actual temporary files
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"temporary content")
        
        temp_dir = tempfile.mkdtemp()
        
        # Add temp paths to state
        base_state["local_temp_path"] = temp_path
        base_state["archive_temp_dir"] = temp_dir
        
        # Verify files exist before cleanup
        assert os.path.exists(temp_path)
        assert os.path.exists(temp_dir)
        
        result = await finalizer(base_state)
        
        # Verify files are cleaned up
        assert not os.path.exists(temp_path)
        assert not os.path.exists(temp_dir)
    
    @pytest.mark.asyncio
    async def test_cleanup_exception_handling(self, base_state, finalizer):
        """TC-F004: 验证清理失败不影响主流程 (P1)"""
        # Set non-existent paths that will cause cleanup to fail
        base_state["local_temp_path"] = "/non/existent/path/file.tmp"
        base_state["archive_temp_dir"] = "/non/existent/path/dir"
        
        # Should not raise exception
        result = await finalizer(base_state)
        
        # Should complete successfully despite cleanup failures
        assert result["processing_stage"] == "completed"
        assert result["progress"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_partial_cleanup_paths(self, base_state, finalizer):
        """Test cleanup when only some paths are present."""
        # Only set temp file path, not archive dir
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            base_state["local_temp_path"] = temp_file.name
            temp_file.write(b"content")
        
        # Don't set archive_temp_dir
        
        result = await finalizer(base_state)
        
        # Should handle partial paths gracefully
        assert result["processing_stage"] == "completed"
        assert not os.path.exists(base_state["local_temp_path"])
    
    @pytest.mark.asyncio
    async def test_no_temp_paths_cleanup(self, base_state, finalizer):
        """Test cleanup when no temp paths are set."""
        # Don't set any temp paths
        
        result = await finalizer(base_state)
        
        # Should complete without issues
        assert result["processing_stage"] == "completed"


class TestSSENotifications:
    """Test SSE progress notification functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_sse_progress_notification(self, base_state, finalizer):
        """TC-F005: 验证SSE通知的触发 (P2)"""
        # Mock SSE notification system
        with patch.object(finalizer, "_notify_progress") as mock_notify:
            result = await finalizer(base_state)
            
            # Verify notification was called
            mock_notify.assert_called_once_with(result)
    
    @pytest.mark.asyncio
    async def test_sse_notification_failure(self, base_state, finalizer):
        """Test handling of SSE notification failures."""
        # Mock notification to fail
        with patch.object(finalizer, "_notify_progress", side_effect=Exception("SSE failed")):
            # Current implementation propagates exceptions
            with pytest.raises(Exception, match="SSE failed"):
                await finalizer(base_state)


class TestMetricsRecording:
    """Test metrics recording functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_success_metric_recording(self, base_state, finalizer):
        """Test success metrics are recorded."""
        # State with no errors
        base_state["error_log"] = []
        
        with patch("core.ingestion.nodes.finalizer.ingest_requests") as mock_metrics:
            mock_counter = Mock()
            mock_metrics.labels.return_value = mock_counter
            
            result = await finalizer(base_state)
            
            # Should record success metric
            mock_metrics.labels.assert_called_with(stage="finalizer", status="success")
            mock_counter.inc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_with_errors_metric_recording(self, base_state, finalizer):
        """Test metrics when errors are present."""
        # State with errors
        base_state["error_log"] = [
            {"stage": "parser", "error": "Some error"},
            {"stage": "embedder", "error": "Another error"},
        ]
        
        with patch("core.ingestion.nodes.finalizer.ingest_requests") as mock_metrics:
            mock_counter = Mock()
            mock_metrics.labels.return_value = mock_counter
            
            result = await finalizer(base_state)
            
            # Should record with_errors metric
            mock_metrics.labels.assert_called_with(stage="finalizer", status="with_errors")
            mock_counter.inc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_metrics_unavailable(self, base_state, finalizer):
        """Test behavior when metrics are unavailable."""
        with patch("core.ingestion.nodes.finalizer.ingest_requests", None):
            # Should complete without error
            result = await finalizer(base_state)
            
            assert result["processing_stage"] == "completed"


class TestDurationMetrics:
    """Test duration metrics functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_duration_metric_recording(self, base_state, finalizer):
        """Test duration metrics are recorded."""
        with patch("core.ingestion.nodes.finalizer.ingest_duration") as mock_duration:
            mock_timer = Mock()
            mock_timer.__enter__ = Mock(return_value=mock_timer)
            mock_timer.__exit__ = Mock(return_value=None)
            mock_duration.labels.return_value.time.return_value = mock_timer
            
            result = await finalizer(base_state)
            
            # Should record duration
            mock_duration.labels.assert_called_with(stage="finalizer")
            mock_duration.labels.return_value.time.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_duration_metrics_unavailable(self, base_state, finalizer):
        """Test behavior when duration metrics are unavailable."""
        with patch("core.ingestion.nodes.finalizer.ingest_duration", None):
            # Should complete without error
            result = await finalizer(base_state)
            
            assert result["processing_stage"] == "completed"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_empty_chunks_handling(self, base_state, finalizer):
        """Test handling of empty chunks list."""
        base_state["chunks"] = []
        
        result = await finalizer(base_state)
        
        assert result["progress"]["total_chunks"] == 0
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_missing_chunks(self, base_state, finalizer):
        """Test handling when chunks are missing."""
        del base_state["chunks"]
        
        result = await finalizer(base_state)
        
        # Should handle gracefully
        assert result["progress"]["total_chunks"] == 0
    
    @pytest.mark.asyncio
    async def test_missing_error_log(self, base_state, finalizer):
        """Test handling when error_log is missing."""
        del base_state["error_log"]
        
        result = await finalizer(base_state)
        
        # Should handle gracefully
        assert result["progress"]["error_count"] == 0
    
    @pytest.mark.asyncio
    async def test_malformed_progress_data(self, base_state, finalizer):
        """Test handling of malformed progress data."""
        base_state["progress"] = {
            "indexed_vector": "invalid",  # Should be int
            "indexed_keyword": None,      # Should be int
        }
        
        result = await finalizer(base_state)
        
        # Should complete without crashing
        assert result["processing_stage"] == "completed"
        assert isinstance(result["progress"]["total_chunks"], int)


class TestCleanupUtilities:
    """Test cleanup utility functions."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_file_cleanup_with_permissions_error(self, base_state, finalizer):
        """Test file cleanup when permission denied."""
        # Create a file and make it read-only (simulate permission error)
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        base_state["local_temp_path"] = temp_path
        
        # Mock os.remove to raise PermissionError
        with patch("os.remove", side_effect=PermissionError("Permission denied")):
            # Should not raise exception
            result = await finalizer(base_state)
            
            assert result["processing_stage"] == "completed"
        
        # Clean up manually
        try:
            os.remove(temp_path)
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_directory_cleanup_with_shutil_error(self, base_state, finalizer):
        """Test directory cleanup when shutil fails."""
        temp_dir = tempfile.mkdtemp()
        base_state["archive_temp_dir"] = temp_dir
        
        # Mock shutil.rmtree to raise exception
        with patch("shutil.rmtree", side_effect=OSError("Directory busy")):
            # Should not raise exception
            result = await finalizer(base_state)
            
            assert result["processing_stage"] == "completed"
        
        # Clean up manually
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


class TestProgressFieldCalculation:
    """Test progress field calculation logic."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [{"stage": "parser", "error": "Minor warning"}],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_default_progress_values(self, base_state, finalizer):
        """Test default values when progress fields are missing."""
        # Remove progress fields
        base_state["progress"] = {}
        
        result = await finalizer(base_state)
        
        progress = result["progress"]
        
        # Should have default values
        assert progress["indexed_vector"] == 0
        assert progress["indexed_keyword"] == 0
        assert progress["total_chunks"] == 10  # From chunks
        assert progress["error_count"] == 1    # From error_log
    
    @pytest.mark.asyncio
    async def test_existing_progress_preservation(self, base_state, finalizer):
        """Test that existing progress values are preserved."""
        base_state["progress"]["custom_field"] = "preserved_value"
        base_state["progress"]["indexed_vector"] = 15
        
        result = await finalizer(base_state)
        
        progress = result["progress"]
        
        # Should preserve existing values
        assert progress["custom_field"] == "preserved_value"
        assert progress["indexed_vector"] == 15
        
        # Should add new required fields
        assert progress["status"] == "completed"
        assert progress["total_chunks"] == 10


class TestNotificationIntegration:
    """Test notification system integration."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_notification_payload(self, base_state, finalizer):
        """Test notification payload contains correct data."""
        notification_data = None
        
        async def capture_notification(state):
            nonlocal notification_data
            notification_data = state["progress"]
        
        with patch.object(finalizer, "_notify_progress", side_effect=capture_notification):
            result = await finalizer(base_state)
            
            # Verify notification was called with correct data
            assert notification_data is not None
            assert notification_data["status"] == "completed"
            assert notification_data["total_chunks"] == 10
    
    @pytest.mark.asyncio
    async def test_notification_exception_isolation(self, base_state, finalizer):
        """Test that notification exceptions propagate (current behavior)."""
        call_count = 0
        
        async def failing_notification(state):
            nonlocal call_count
            call_count += 1
            raise Exception("Notification service down")
        
        with patch.object(finalizer, "_notify_progress", side_effect=failing_notification):
            # Current implementation propagates exceptions
            with pytest.raises(Exception, match="Notification service down"):
                await finalizer(base_state)
            
            assert call_count == 1  # Notification was attempted


class TestStateConsistency:
    """Test state consistency after finalization."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_state_immutability(self, base_state, finalizer):
        """Test that original state structure is preserved."""
        original_keys = set(base_state.keys())
        
        result = await finalizer(base_state)
        
        # Should preserve all original keys
        for key in original_keys:
            assert key in result
        
        # Should add processing_stage update
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_nested_object_preservation(self, base_state, finalizer):
        """Test that nested objects are properly handled."""
        # Add nested structure
        base_state["nested"] = {
            "level1": {
                "level2": ["item1", "item2"]
            }
        }
        
        result = await finalizer(base_state)
        
        # Should preserve nested structure
        assert result["nested"]["level1"]["level2"] == ["item1", "item2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# =============================================================================
# NEW: Robustness and Edge Case Tests
# =============================================================================

class TestIdempotentCleanup:
    """Test idempotent cleanup behavior."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}"}
                for i in range(10)
            ],
            "error_log": [
                {"stage": "parser", "error": "Minor parsing warning"},
            ],
            "quality_metrics": {
                "original_count": 15,
                "removed_count": 5,
            },
            "progress": {
                "indexed_vector": 8,
                "indexed_keyword": 10,
            },
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_double_cleanup_idempotency(self, base_state, finalizer):
        """TC-F006: 验证重复cleanup的幂等性 (P0)"""
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"content")
        
        base_state["local_temp_path"] = temp_path
        
        # First cleanup
        result1 = await finalizer(base_state)
        assert result1["processing_stage"] == "completed"
        
        # Second cleanup (file already deleted)
        result2 = await finalizer(base_state)
        assert result2["processing_stage"] == "completed"
        
        # Both should succeed without errors
        assert result1["progress"]["status"] == "completed"
        assert result2["progress"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_cleanup_already_deleted_directory(self, base_state, finalizer):
        """TC-F007: 验证清理已删除目录的幂等性 (P1)"""
        temp_dir = tempfile.mkdtemp()
        base_state["archive_temp_dir"] = temp_dir
        
        # Delete directory before cleanup
        import shutil
        shutil.rmtree(temp_dir)
        
        # Cleanup should not fail
        result = await finalizer(base_state)
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_multiple_finalize_calls(self, base_state, finalizer):
        """TC-F008: 验证多次finalize调用的安全性 (P1)"""
        results = []
        
        for _ in range(3):
            result = await finalizer(base_state)
            results.append(result)
        
        # All calls should succeed
        for result in results:
            assert result["processing_stage"] == "completed"
            assert result["progress"]["status"] == "completed"


class TestMissingIdentifiers:
    """Test handling of missing channel_id and task_id."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_missing_channel_id_safe_exit(self, base_state, finalizer):
        """TC-F009: 验证缺失channel_id时的安全退出 (P0)"""
        del base_state["channel_id"]
        
        result = await finalizer(base_state)
        
        # Should complete without errors
        assert result["processing_stage"] == "completed"
        assert result["progress"]["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_missing_task_id_safe_exit(self, base_state, finalizer):
        """TC-F010: 验证缺失task_id时的安全退出 (P0)"""
        del base_state["task_id"]
        
        result = await finalizer(base_state)
        
        # Should complete without errors
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_missing_both_identifiers(self, base_state, finalizer):
        """TC-F011: 验证同时缺失channel_id和task_id的处理 (P1)"""
        del base_state["channel_id"]
        del base_state["task_id"]
        
        result = await finalizer(base_state)
        
        # Should still complete
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_empty_string_identifiers(self, base_state, finalizer):
        """TC-F012: 验证空字符串标识符的处理 (P1)"""
        base_state["channel_id"] = ""
        base_state["task_id"] = ""
        
        result = await finalizer(base_state)
        
        # Should complete without errors
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_none_identifiers(self, base_state, finalizer):
        """TC-F013: 验证None标识符的处理 (P1)"""
        base_state["channel_id"] = None
        base_state["task_id"] = None
        
        result = await finalizer(base_state)
        
        # Should complete without errors
        assert result["processing_stage"] == "completed"


class TestNotificationFailureHandling:
    """Test handling of notification and metrics failures."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_notification_failure_logging(self, base_state, finalizer):
        """TC-F014: 验证通知失败时异常传播 (P1)"""
        # Mock notification to fail
        async def failing_notify(state):
            raise Exception("Notification service unavailable")
        
        with patch.object(finalizer, "_notify_progress", side_effect=failing_notify):
            # Current implementation propagates exceptions
            with pytest.raises(Exception, match="Notification service unavailable"):
                await finalizer(base_state)
    
    @pytest.mark.asyncio
    async def test_metrics_failure_continuation(self, base_state, finalizer):
        """TC-F015: 验证指标记录失败时异常传播 (P1)"""
        with patch("core.ingestion.nodes.finalizer.ingest_requests") as mock_metrics:
            mock_metrics.labels.side_effect = Exception("Metrics service down")
            
            # Current implementation propagates exceptions
            with pytest.raises(Exception, match="Metrics service down"):
                await finalizer(base_state)
    
    @pytest.mark.asyncio
    async def test_duration_metrics_failure(self, base_state, finalizer):
        """TC-F016: 验证时长指标失败时异常传播 (P1)"""
        with patch("core.ingestion.nodes.finalizer.ingest_duration") as mock_duration:
            mock_duration.labels.side_effect = Exception("Duration metrics failed")
            
            # Current implementation propagates exceptions
            with pytest.raises(Exception, match="Duration metrics failed"):
                await finalizer(base_state)


class TestCleanupEdgeCases:
    """Test cleanup edge cases."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_cleanup_symlink(self, base_state, finalizer):
        """TC-F017: 验证符号链接的清理 (P2)"""
        # Create temp file and symlink
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        symlink_path = temp_path + "_link"
        try:
            os.symlink(temp_path, symlink_path)
            base_state["local_temp_path"] = symlink_path
            
            result = await finalizer(base_state)
            
            # Should handle symlink cleanup
            assert result["processing_stage"] == "completed"
        finally:
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass
            try:
                os.remove(symlink_path)
            except:
                pass
    
    @pytest.mark.asyncio
    async def test_cleanup_nested_directory(self, base_state, finalizer):
        """TC-F018: 验证嵌套目录的清理 (P1)"""
        # Create nested directory structure
        temp_dir = tempfile.mkdtemp()
        nested_dir = os.path.join(temp_dir, "level1", "level2", "level3")
        os.makedirs(nested_dir)
        
        # Create files in nested structure
        with open(os.path.join(nested_dir, "file.txt"), "w") as f:
            f.write("content")
        
        base_state["archive_temp_dir"] = temp_dir
        
        result = await finalizer(base_state)
        
        # Should clean up entire nested structure
        assert result["processing_stage"] == "completed"
        assert not os.path.exists(temp_dir)
    
    @pytest.mark.asyncio
    async def test_cleanup_with_open_file_handle(self, base_state, finalizer):
        """TC-F019: 验证文件句柄打开时的清理 (P2)"""
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = temp_file.name
        # Keep file handle open
        
        base_state["local_temp_path"] = temp_path
        
        try:
            result = await finalizer(base_state)
            
            # Should handle gracefully (may or may not delete depending on OS)
            assert result["processing_stage"] == "completed"
        finally:
            temp_file.close()
            try:
                os.remove(temp_path)
            except:
                pass


class TestProgressCalculation:
    """Test progress calculation edge cases."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_negative_progress_values(self, base_state, finalizer):
        """TC-F020: 验证负数进度值的处理 (P1)"""
        base_state["progress"] = {
            "indexed_vector": -5,
            "indexed_keyword": -10,
        }
        
        result = await finalizer(base_state)
        
        # Should handle negative values
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_very_large_chunk_count(self, base_state, finalizer):
        """TC-F021: 验证超大chunk数量的处理 (P1)"""
        # Create state with many chunks
        base_state["chunks"] = [{"id": f"chunk_{i}"} for i in range(100000)]
        
        result = await finalizer(base_state)
        
        assert result["progress"]["total_chunks"] == 100000
        assert result["processing_stage"] == "completed"
    
    @pytest.mark.asyncio
    async def test_float_progress_values(self, base_state, finalizer):
        """TC-F022: 验证浮点数进度值的处理 (P1)"""
        base_state["progress"] = {
            "indexed_vector": 5.5,
            "indexed_keyword": 10.9,
        }
        
        result = await finalizer(base_state)
        
        # Should handle float values
        assert result["processing_stage"] == "completed"


class TestQualityMetricsHandling:
    """Test quality metrics handling."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_empty_quality_metrics(self, base_state, finalizer):
        """TC-F023: 验证空质量指标的处理 (P1)"""
        base_state["quality_metrics"] = {}
        
        result = await finalizer(base_state)
        
        # Should handle empty metrics
        assert result["processing_stage"] == "completed"
        # Should not have quality fields or have them as 0
        assert result["progress"].get("quality_original", 0) == 0
    
    @pytest.mark.asyncio
    async def test_partial_quality_metrics(self, base_state, finalizer):
        """TC-F024: 验证部分质量指标的处理 (P1)"""
        base_state["quality_metrics"] = {
            "original_count": 100,
            # Missing removed_count
        }
        
        result = await finalizer(base_state)
        
        # Should handle partial metrics
        assert result["processing_stage"] == "completed"
        assert result["progress"]["quality_original"] == 100
    
    @pytest.mark.asyncio
    async def test_quality_metrics_with_extra_fields(self, base_state, finalizer):
        """TC-F025: 验证额外质量指标字段的处理 (P1)"""
        base_state["quality_metrics"] = {
            "original_count": 100,
            "removed_count": 20,
            "extra_field": "should_be_ignored",
            "another_field": 12345,
        }
        
        result = await finalizer(base_state)
        
        # Should process standard fields
        assert result["progress"]["quality_original"] == 100
        assert result["progress"]["quality_filtered"] == 20
        assert result["processing_stage"] == "completed"


class TestConcurrentFinalization:
    """Test concurrent finalization scenarios."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for finalizer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "processing_stage": "index",
            "chunks": [{"id": f"chunk_{i}", "content": f"Content {i}"} for i in range(10)],
            "error_log": [],
            "quality_metrics": {},
            "progress": {},
        }
    
    @pytest.fixture
    def finalizer(self) -> Finalizer:
        """Finalizer instance."""
        return Finalizer()
    
    @pytest.mark.asyncio
    async def test_concurrent_finalize_same_state(self, base_state, finalizer):
        """TC-F026: 验证并发finalize同一状态的安全性 (P2)"""
        import asyncio
        
        # Run multiple finalizations concurrently
        tasks = [finalizer(base_state.copy()) for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without exceptions
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent finalization raised exception: {result}")
            assert result["processing_stage"] == "completed"
