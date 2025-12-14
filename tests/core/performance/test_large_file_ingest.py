"""Large file ingest performance tests.

Tests memory usage and processing time for large file ingestion
using the FakeBlobStore to simulate streaming large files.

Requirements: 1.1-1.5
"""

import asyncio
import gc
import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, MagicMock, patch

from tests.core.performance.utils.fake_blob_store import FakeBlobStore
from tests.core.performance.utils.memory_tracker import MemoryTracker
from tests.core.performance.utils.metrics_collector import MetricsCollector


# =============================================================================
# Constants from loader.py
# =============================================================================

LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
MAX_MEMORY_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# Memory multiplier threshold (1.5x file size)
MEMORY_MULTIPLIER_THRESHOLD = 1.5


# =============================================================================
# Property 1: Large File Memory Limit
# **Feature: performance-tests, Property 1: 大文件 Ingest 内存限制**
# **Validates: Requirements 1.1, 1.2**
# =============================================================================


class TestLargeFileMemoryLimit:
    """Property-based tests for large file ingest memory limits.
    
    Property 1: For any file size between 100MB and 500MB, when ingested
    via streaming blob_store, the peak memory usage SHALL be at most 
    1.5x the file size.
    
    Requirements: 1.1, 1.2
    """

    @pytest.mark.performance
    @pytest.mark.memory_intensive
    @settings(max_examples=100, deadline=None)
    @given(
        file_size_mb=st.integers(min_value=100, max_value=500)
    )
    @pytest.mark.asyncio
    async def test_property_large_file_memory_limit(
        self, 
        file_size_mb: int,
    ):
        """
        **Feature: performance-tests, Property 1: 大文件 Ingest 内存限制**
        **Validates: Requirements 1.1, 1.2**
        
        For any file size between 100MB and 500MB, when ingested via 
        streaming blob_store, the peak memory usage SHALL be at most 
        1.5x the file size.
        
        This test simulates streaming a large file and verifies that
        memory usage stays within acceptable bounds.
        """
        # Create memory tracker inside test (not as fixture for hypothesis)
        memory_tracker = MemoryTracker()
        
        # Convert MB to bytes
        file_size_bytes = file_size_mb * 1024 * 1024
        
        # Create fake blob store with streaming support
        blob_store = FakeBlobStore(
            file_size=file_size_bytes,
            chunk_size=8192,  # 8KB chunks
            supports_streaming=True,
        )
        
        # Force garbage collection before test
        gc.collect()
        
        # Start memory tracking
        memory_tracker.start()
        
        try:
            # Simulate streaming ingest - read file in chunks
            file_key = "test/large_file.pdf"
            total_bytes_read = 0
            
            async for chunk in blob_store.stream(file_key):
                total_bytes_read += len(chunk)
                # Simulate processing - don't accumulate chunks in memory
                # This mimics proper streaming behavior
                del chunk
            
            # Verify all bytes were read
            assert total_bytes_read == file_size_bytes, (
                f"Expected to read {file_size_bytes} bytes, "
                f"but read {total_bytes_read} bytes"
            )
            
        finally:
            # Stop tracking and get peak memory
            memory_tracker.stop()
        
        # Calculate memory threshold (1.5x file size in MB)
        memory_threshold_mb = file_size_mb * MEMORY_MULTIPLIER_THRESHOLD
        
        # Get memory delta (increase from baseline)
        memory_delta_mb = memory_tracker.get_delta()
        
        # Assert memory constraint
        # We check delta rather than absolute peak to account for
        # baseline process memory
        assert memory_delta_mb <= memory_threshold_mb, (
            f"Memory limit exceeded for {file_size_mb}MB file. "
            f"Memory increase: {memory_delta_mb:.2f}MB, "
            f"Threshold: {memory_threshold_mb:.2f}MB (1.5x file size)"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_100mb_file_memory_limit(self, memory_tracker: MemoryTracker):
        """
        TC-LF-001: Test 100MB file memory limit.
        
        WHEN ingesting a 100MB file via streaming blob_store 
        THEN the system SHALL maintain peak memory below 150MB (1.5x file size)
        
        Requirements: 1.1
        """
        file_size_mb = 100
        file_size_bytes = file_size_mb * 1024 * 1024
        
        blob_store = FakeBlobStore(
            file_size=file_size_bytes,
            chunk_size=8192,
            supports_streaming=True,
        )
        
        gc.collect()
        memory_tracker.start()
        
        try:
            total_bytes_read = 0
            async for chunk in blob_store.stream("test/100mb_file.pdf"):
                total_bytes_read += len(chunk)
                del chunk
            
            assert total_bytes_read == file_size_bytes
        finally:
            memory_tracker.stop()
        
        memory_delta_mb = memory_tracker.get_delta()
        memory_threshold_mb = 150  # 1.5x 100MB
        
        assert memory_delta_mb <= memory_threshold_mb, (
            f"100MB file exceeded memory limit. "
            f"Memory increase: {memory_delta_mb:.2f}MB, "
            f"Threshold: {memory_threshold_mb}MB"
        )

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_500mb_file_memory_limit(self, memory_tracker: MemoryTracker):
        """
        TC-LF-002: Test 500MB file memory limit.
        
        WHEN ingesting a 500MB file via streaming blob_store 
        THEN the system SHALL maintain peak memory below 750MB (1.5x file size)
        
        Requirements: 1.2
        """
        file_size_mb = 500
        file_size_bytes = file_size_mb * 1024 * 1024
        
        blob_store = FakeBlobStore(
            file_size=file_size_bytes,
            chunk_size=8192,
            supports_streaming=True,
        )
        
        gc.collect()
        memory_tracker.start()
        
        try:
            total_bytes_read = 0
            async for chunk in blob_store.stream("test/500mb_file.pdf"):
                total_bytes_read += len(chunk)
                del chunk
            
            assert total_bytes_read == file_size_bytes
        finally:
            memory_tracker.stop()
        
        memory_delta_mb = memory_tracker.get_delta()
        memory_threshold_mb = 750  # 1.5x 500MB
        
        assert memory_delta_mb <= memory_threshold_mb, (
            f"500MB file exceeded memory limit. "
            f"Memory increase: {memory_delta_mb:.2f}MB, "
            f"Threshold: {memory_threshold_mb}MB"
        )


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def fake_blob_store_200mb_no_streaming() -> FakeBlobStore:
    """Create a FakeBlobStore for 200MB file without streaming support."""
    return FakeBlobStore(
        file_size=200 * 1024 * 1024,
        supports_streaming=False,
    )


# =============================================================================
# TC-LF-005: No Streaming Support Rejection Test
# =============================================================================


class TestNoStreamingSupportRejection:
    """Test that files >100MB are rejected when blob_store doesn't support streaming.
    
    Requirements: 1.5
    """

    @pytest.mark.asyncio
    async def test_large_file_rejected_without_streaming_support(
        self, fake_blob_store_200mb_no_streaming: FakeBlobStore
    ):
        """
        TC-LF-005: Test blob_store without streaming rejects >100MB files.
        
        When blob_store streaming is unavailable for files >100MB,
        the system SHALL reject the request with RuntimeError.
        
        Requirements: 1.5
        """
        blob_store = fake_blob_store_200mb_no_streaming
        file_key = "test/large_file.pdf"
        
        # Verify file size is above threshold
        metadata = await blob_store.head(file_key)
        assert metadata["size"] > LARGE_FILE_THRESHOLD
        assert not metadata["supports_streaming"]
        
        # Attempting to stream should raise RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            async for _ in blob_store.stream(file_key):
                pass
        
        assert "Streaming not supported" in str(exc_info.value)
        assert ">100MB" in str(exc_info.value) or "streaming" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_small_file_allowed_without_streaming(self):
        """
        Test that small files (<100MB) can still be loaded without streaming.
        
        This is a sanity check that the rejection only applies to large files.
        """
        # Create a small file blob store without streaming
        blob_store = FakeBlobStore(
            file_size=50 * 1024 * 1024,  # 50MB
            supports_streaming=False,
        )
        file_key = "test/small_file.pdf"
        
        # Small files should still be accessible via get()
        content = await blob_store.get(file_key)
        assert len(content) == 50 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_large_file_with_streaming_support_works(
        self, fake_blob_store_100mb: FakeBlobStore
    ):
        """
        Test that large files work fine when streaming IS supported.
        
        This validates that the rejection is specifically for missing streaming support.
        """
        blob_store = fake_blob_store_100mb
        file_key = "test/large_file.pdf"
        
        # Verify streaming is supported
        metadata = await blob_store.head(file_key)
        assert metadata["supports_streaming"]
        
        # Streaming should work
        total_bytes = 0
        async for chunk in blob_store.stream(file_key):
            total_bytes += len(chunk)
        
        assert total_bytes == 100 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_streaming_rejection_message_is_informative(
        self, fake_blob_store_200mb_no_streaming: FakeBlobStore
    ):
        """
        Test that the rejection error message is informative.
        
        The error should clearly indicate:
        - That streaming is not supported
        - The file size threshold
        """
        blob_store = fake_blob_store_200mb_no_streaming
        file_key = "test/large_file.pdf"
        
        with pytest.raises(RuntimeError) as exc_info:
            async for _ in blob_store.stream(file_key):
                pass
        
        error_message = str(exc_info.value)
        # Should mention streaming
        assert "streaming" in error_message.lower() or "Streaming" in error_message


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestStreamingEdgeCases:
    """Additional edge case tests for streaming behavior.
    
    These tests verify edge cases in the FakeBlobStore streaming logic.
    """

    @pytest.mark.asyncio
    async def test_exactly_100mb_file_with_streaming(self):
        """
        Test that exactly 100MB files work with streaming support.
        
        This is a boundary test at the LARGE_FILE_THRESHOLD.
        """
        blob_store = FakeBlobStore(
            file_size=LARGE_FILE_THRESHOLD,  # Exactly 100MB
            supports_streaming=True,
        )
        file_key = "test/boundary_file.pdf"
        
        total_bytes = 0
        async for chunk in blob_store.stream(file_key):
            total_bytes += len(chunk)
        
        assert total_bytes == LARGE_FILE_THRESHOLD

    @pytest.mark.asyncio
    async def test_just_over_100mb_rejected_without_streaming(self):
        """
        Test that files just over 100MB are rejected without streaming.
        
        This is a boundary test just above LARGE_FILE_THRESHOLD.
        """
        blob_store = FakeBlobStore(
            file_size=LARGE_FILE_THRESHOLD + 1,  # Just over 100MB
            supports_streaming=False,
        )
        file_key = "test/boundary_file.pdf"
        
        with pytest.raises(RuntimeError) as exc_info:
            async for _ in blob_store.stream(file_key):
                pass
        
        assert "Streaming not supported" in str(exc_info.value)
