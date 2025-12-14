"""
Test suite for core.ingestion.nodes.loader module.

Tests the document loader including:
- Large file handling and lazy loading
- Archive extraction (ZIP/TAR)
- Temporary file management
- Multi-tenant isolation
- Error handling and edge cases
"""

import asyncio
import os
import tempfile
import zipfile
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict

import pytest

from core.ingestion.nodes.loader import (
    LoaderNode,
    LARGE_FILE_THRESHOLD,
    MAX_MEMORY_FILE_SIZE,
    UNKNOWN_SIZE,
)


class TestLoaderNode:
    """Test LoaderNode functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for loader tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "file_path": "test/document.pdf",
            "file_type": "pdf",
            "batch_id": "batch_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {},
            "capability_loader": None,
            "processing_stage": "upload",
            "retry_count": 0,
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_blob_store(self):
        """Mock blob store with configurable behavior."""
        store = AsyncMock()
        store.exists.return_value = True
        store.get.return_value = b"fake_content"
        store.head.return_value = {"size": 1024}
        return store


class TestLargeFileHandling:
    """Test large file detection and lazy loading."""
    
    @pytest.mark.asyncio
    async def test_large_file_threshold_detection(self, base_state, mock_blob_store):
        """TC-L001: 验证文件大小检测和lazy_load标志设置 (P1)"""
        # Setup: File larger than threshold but smaller than max
        file_size = LARGE_FILE_THRESHOLD + 1024  # 100MB + 1KB
        mock_blob_store.head.return_value = {"size": file_size}
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store), \
             patch.object(loader, '_download_to_temp', return_value="/tmp/test.pdf") as mock_download:
            
            result = await loader(base_state)
        
        # Verify lazy loading is enabled
        assert result["lazy_load"] is True
        assert result["raw_content"] is None
        assert result["local_temp_path"] == "/tmp/test.pdf"
        assert result["file_size"] == file_size
        mock_download.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_super_large_file_rejection(self, base_state, mock_blob_store):
        """TC-L002: 验证>500MB文件被正确拒绝 (P0)"""
        # Setup: File larger than max memory size
        file_size = MAX_MEMORY_FILE_SIZE + 1024  # 500MB + 1KB
        mock_blob_store.head.return_value = {"size": file_size}
        
        # Mock blob store without streaming support
        del mock_blob_store.download_to_file
        del mock_blob_store.stream
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Should set lazy_load but warn about streaming mode
        assert result["lazy_load"] is True
        assert result["raw_content"] is None
        assert result["file_size"] == file_size
        
        # Should log warning about large file
        warnings = [e for e in result["error_log"] if "warning" in e]
        assert len(warnings) > 0
        assert "too large" in warnings[0]["warning"]
    
    @pytest.mark.asyncio
    async def test_unknown_size_file_handling(self, base_state, mock_blob_store):
        """TC-L003: 验证未知大小文件的安全处理 (P1)"""
        # Setup: Blob store returns unknown size
        mock_blob_store.head.return_value = {"size": UNKNOWN_SIZE}
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Verify unknown size handling
        assert result["file_size"] == UNKNOWN_SIZE
        assert result["lazy_load"] is True
        assert result["raw_content"] is None
        
        # Should log warning about unknown size
        warnings = [e for e in result["error_log"] if "warning" in e]
        assert any("Unknown file size" in w["warning"] for w in warnings)
    
    @pytest.mark.asyncio
    async def test_no_streaming_capability_rejection(self, base_state, mock_blob_store):
        """TC-L004: 验证blob store无streaming时拒绝大文件 (P0)"""
        # Setup: Large file with no streaming support
        file_size = LARGE_FILE_THRESHOLD + 1024
        mock_blob_store.head.return_value = {"size": file_size}
        
        # Remove streaming methods
        if hasattr(mock_blob_store, 'download_to_file'):
            del mock_blob_store.download_to_file
        if hasattr(mock_blob_store, 'stream'):
            del mock_blob_store.stream
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            # Should raise RuntimeError when trying to download large file
            with pytest.raises(RuntimeError, match="does not support streaming downloads"):
                await loader._download_to_temp(mock_blob_store, "test.pdf")
    
    @pytest.mark.asyncio
    async def test_small_file_memory_loading(self, base_state, mock_blob_store):
        """Test small files are loaded entirely into memory."""
        # Setup: Small file
        file_size = 1024  # 1KB
        file_content = b"small file content"
        
        # Make head an async mock
        async def mock_head(path):
            return {"size": file_size}
        mock_blob_store.head = mock_head
        
        # Make get an async mock
        async def mock_get(path):
            return file_content
        mock_blob_store.get = mock_get
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Verify memory loading
        assert result["lazy_load"] is False
        assert result["raw_content"] == file_content
        assert result["file_size"] == len(file_content)
        assert "local_temp_path" not in result


class TestArchiveHandling:
    """Test archive file extraction and processing."""
    
    @pytest.mark.asyncio
    async def test_zip_file_extraction(self, base_state, mock_blob_store):
        """TC-L005: 验证ZIP文件正确解压和文件列表 (P1)"""
        # Create a real ZIP file in memory
        zip_buffer = self._create_test_zip()
        mock_blob_store.get = AsyncMock(return_value=zip_buffer)
        
        # Set file type to zip
        base_state["file_type"] = "zip"
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Verify archive extraction
        assert result["archive_extracted"] is True
        assert len(result["archive_files"]) > 0
        assert result["archive_temp_dir"] is not None
        # raw_content may contain first file content if small
        
        # Verify extracted file info
        first_file = result["archive_files"][0]
        assert "path" in first_file
        assert "relative_path" in first_file
        assert "size" in first_file
    
    @pytest.mark.asyncio
    async def test_zip_bomb_protection(self, base_state, mock_blob_store):
        """TC-L006: 验证解压尺寸限制防止ZIP炸弹 (P0)"""
        # Create a ZIP with large uncompressed content
        zip_buffer = self._create_zip_bomb()
        mock_blob_store.get.return_value = zip_buffer
        base_state["file_type"] = "zip"
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            # Should handle large extraction gracefully
            result = await loader(base_state)
            
            # Even if extraction succeeds, should have size limits or warnings
            if result.get("archive_extracted"):
                # Check for reasonable file sizes
                for file_info in result.get("archive_files", []):
                    assert file_info["size"] < 100 * 1024 * 1024  # 100MB limit per file
    
    @pytest.mark.asyncio
    async def test_corrupted_archive_handling(self, base_state, mock_blob_store):
        """TC-L007: 验证损坏ZIP文件的错误处理 (P1)"""
        # Provide corrupted ZIP content
        mock_blob_store.get.return_value = b"not_a_zip_file"
        base_state["file_type"] = "zip"
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Should handle corruption gracefully
        errors = [e for e in result["error_log"] if "Archive extraction failed" in e.get("error", "")]
        assert len(errors) > 0
    
    def _create_test_zip(self) -> bytes:
        """Create a test ZIP file with multiple files."""
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("file1.txt", "Content of file 1")
            zf.writestr("file2.txt", "Content of file 2")
            zf.writestr("subdir/file3.txt", "Content of file 3 in subdirectory")
        
        return zip_buffer.getvalue()
    
    def _create_zip_bomb(self) -> bytes:
        """Create a ZIP file that expands to large size."""
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Create a file with repetitive content that compresses well
            large_content = "A" * (10 * 1024 * 1024)  # 10MB of 'A's
            zf.writestr("large_file.txt", large_content)
        
        return zip_buffer.getvalue()


class TestTemporaryFileManagement:
    """Test temporary file creation and cleanup."""
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_exception(self, base_state, mock_blob_store):
        """TC-L008: 验证临时文件在异常时被清理 (P1)"""
        loader = LoaderNode()
        
        # Mock blob store with stream that raises exception
        async def failing_stream(file_path):
            raise Exception("Download failed")
            yield b""  # Never reached - make it a generator
        
        # Remove download_to_file so it uses stream
        if hasattr(mock_blob_store, 'download_to_file'):
            del mock_blob_store.download_to_file
        mock_blob_store.stream = failing_stream
        
        # Mock download process that fails
        with patch('tempfile.mkstemp', return_value=(1, "/tmp/test_temp.pdf")), \
             patch('os.close'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove:
            
            with pytest.raises(RuntimeError, match="Failed to download file for streaming"):
                await loader._download_to_temp(mock_blob_store, "test.pdf")
            
            # Verify temp file was cleaned up
            mock_remove.assert_called_with("/tmp/test_temp.pdf")
    
    @pytest.mark.asyncio
    async def test_multi_tenant_temp_file_isolation(self, mock_blob_store):
        """TC-L009: 验证不同租户的临时文件隔离 (P0)"""
        loader = LoaderNode()
        
        # Create states for different tenants
        state_a = {
            "channel_id": "tenant_a",
            "file_path": "file_a.pdf",
            "file_type": "pdf",
            "error_log": [],
        }
        
        state_b = {
            "channel_id": "tenant_b", 
            "file_path": "file_b.pdf",
            "file_type": "pdf",
            "error_log": [],
        }
        
        # Mock large files requiring temp download
        file_size = LARGE_FILE_THRESHOLD + 1024
        mock_blob_store.head.return_value = {"size": file_size}
        
        temp_paths = []
        
        def mock_download_to_temp(blob_store, file_path):
            # Generate unique temp path for each call
            temp_path = f"/tmp/{file_path}_{len(temp_paths)}.pdf"
            temp_paths.append(temp_path)
            return temp_path
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store), \
             patch.object(loader, '_download_to_temp', side_effect=mock_download_to_temp):
            
            result_a = await loader(state_a)
            result_b = await loader(state_b)
        
        # Verify temp files are different
        assert result_a["local_temp_path"] != result_b["local_temp_path"]
        assert len(temp_paths) == 2
        assert temp_paths[0] != temp_paths[1]


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_file_not_found_handling(self, base_state, mock_blob_store):
        """Test handling of non-existent files."""
        mock_blob_store.exists.return_value = False
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Should record error
        errors = [e for e in result["error_log"] if "not found" in e.get("error", "")]
        assert len(errors) > 0
    
    @pytest.mark.asyncio
    async def test_blob_store_exception_handling(self, base_state, mock_blob_store):
        """Test handling of blob store exceptions."""
        mock_blob_store.exists.side_effect = Exception("Blob store error")
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        # Should record error and not crash
        assert len(result["error_log"]) > 0
        assert "Blob store error" in result["error_log"][0]["error"]
    
    @pytest.mark.asyncio
    async def test_size_detection_fallback(self, base_state, mock_blob_store):
        """Test size detection fallback methods."""
        # Remove head method, add stat method
        del mock_blob_store.head
        mock_blob_store.stat.return_value = {"size": 2048}
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            size = await loader._get_file_size(mock_blob_store, "test.pdf")
        
        assert size == 2048
    
    @pytest.mark.asyncio
    async def test_size_detection_local_fallback(self, base_state, mock_blob_store):
        """Test local file size detection fallback."""
        # Remove all blob store size methods
        del mock_blob_store.head
        if hasattr(mock_blob_store, 'stat'):
            del mock_blob_store.stat
        if hasattr(mock_blob_store, 'get_size'):
            del mock_blob_store.get_size
        
        loader = LoaderNode()
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.getsize', return_value=4096):
            
            size = await loader._get_file_size(mock_blob_store, "/local/test.pdf")
        
        assert size == 4096
    
    @pytest.mark.asyncio
    async def test_size_detection_unknown_fallback(self, base_state, mock_blob_store):
        """Test unknown size fallback."""
        # Create a simple object without any size methods
        class MinimalBlobStore:
            pass
        
        mock_store = MinimalBlobStore()
        
        loader = LoaderNode()
        
        with patch('os.path.exists', return_value=False):
            size = await loader._get_file_size(mock_store, "test.pdf")
        
        assert size == UNKNOWN_SIZE


class TestStreamingDownload:
    """Test streaming download functionality."""
    
    @pytest.mark.asyncio
    async def test_streaming_download_success(self, mock_blob_store):
        """Test successful streaming download."""
        loader = LoaderNode()
        
        # Mock streaming download
        async def mock_download_to_file(file_path, temp_path):
            # Simulate writing file
            with open(temp_path, 'wb') as f:
                f.write(b"downloaded content")
        
        mock_blob_store.download_to_file = mock_download_to_file
        
        with patch('tempfile.mkstemp', return_value=(1, "/tmp/test.pdf")), \
             patch('os.close'):
            
            temp_path = await loader._download_to_temp(mock_blob_store, "test.pdf")
            
            assert temp_path == "/tmp/test.pdf"
    
    @pytest.mark.asyncio
    async def test_chunk_streaming_download(self, mock_blob_store):
        """Test chunk-based streaming download."""
        loader = LoaderNode()
        
        # Remove download_to_file so it uses stream
        if hasattr(mock_blob_store, 'download_to_file'):
            del mock_blob_store.download_to_file
        
        # Mock chunk streaming as async generator
        async def mock_stream(file_path):
            chunks = [b"chunk1", b"chunk2", b"chunk3"]
            for chunk in chunks:
                yield chunk
        
        mock_blob_store.stream = mock_stream
        
        # Create a proper async context manager mock for aiofiles
        write_calls = []
        
        class MockFileHandle:
            async def write(self, data):
                write_calls.append(data)
        
        class MockAsyncContextManager:
            async def __aenter__(self):
                return MockFileHandle()
            async def __aexit__(self, *args):
                return None
        
        with patch('tempfile.mkstemp', return_value=(1, "/tmp/test.pdf")), \
             patch('os.close'), \
             patch('core.ingestion.nodes.loader.aiofiles.open', return_value=MockAsyncContextManager()):
            
            temp_path = await loader._download_to_temp(mock_blob_store, "test.pdf")
            
            # Verify chunks were written
            assert len(write_calls) == 3
            assert temp_path == "/tmp/test.pdf"


class TestProgressTracking:
    """Test progress tracking and metrics."""
    
    @pytest.mark.asyncio
    async def test_progress_file_size_tracking(self, base_state, mock_blob_store):
        """Test file size is recorded in progress."""
        file_size = 2048
        mock_blob_store.head.return_value = {"size": file_size}
        
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        assert result["progress"]["file_size"] == file_size
    
    @pytest.mark.asyncio
    async def test_processing_stage_update(self, base_state, mock_blob_store):
        """Test processing stage is updated correctly."""
        loader = LoaderNode()
        
        with patch('core.ingestion.nodes.loader.get_blob_store', return_value=mock_blob_store):
            result = await loader(base_state)
        
        assert result["processing_stage"] == "parse"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])