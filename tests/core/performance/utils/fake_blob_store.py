"""Fake blob store for performance testing.

Provides a mock blob store that simulates streaming large files
without actual I/O overhead, useful for testing memory and timing
characteristics of the ingest pipeline.
"""

import asyncio
from typing import AsyncIterator


class FakeBlobStore:
    """Fake blob store for performance testing.
    
    Simulates a blob store that can stream large files in chunks,
    allowing tests to verify memory usage and processing time
    without real network or disk I/O.
    
    Attributes:
        file_size: Size of the fake file in bytes.
        chunk_size: Size of each chunk when streaming.
        supports_streaming: Whether streaming is supported.
    """

    def __init__(
        self,
        file_size: int = 100 * 1024 * 1024,  # 100MB default
        chunk_size: int = 8192,
        supports_streaming: bool = True,
    ) -> None:
        """Initialize FakeBlobStore.
        
        Args:
            file_size: Size of the fake file in bytes.
            chunk_size: Size of each chunk when streaming.
            supports_streaming: Whether streaming is supported.
        """
        self.file_size = file_size
        self.chunk_size = chunk_size
        self.supports_streaming = supports_streaming
        self._chunk_data = b"x" * chunk_size  # Pre-allocate chunk

    async def head(self, key: str) -> dict:
        """Return file metadata including size.
        
        Args:
            key: The blob key/path.
            
        Returns:
            Dictionary with file metadata.
        """
        return {
            "key": key,
            "size": self.file_size,
            "content_type": "application/octet-stream",
            "supports_streaming": self.supports_streaming,
        }

    async def get(self, key: str) -> bytes:
        """Return file content (for small files).
        
        Warning: This loads the entire file into memory.
        For large files, use stream() instead.
        
        Args:
            key: The blob key/path.
            
        Returns:
            File content as bytes.
        """
        return b"x" * self.file_size

    async def stream(
        self, key: str, chunk_size: int | None = None
    ) -> AsyncIterator[bytes]:
        """Stream file content in chunks.
        
        Args:
            key: The blob key/path.
            chunk_size: Override default chunk size.
            
        Yields:
            Chunks of file content.
            
        Raises:
            RuntimeError: If streaming is not supported.
        """
        if not self.supports_streaming:
            raise RuntimeError(
                f"Streaming not supported for file: {key}. "
                "Files >100MB require streaming support."
            )
        
        effective_chunk_size = chunk_size or self.chunk_size
        bytes_remaining = self.file_size
        
        while bytes_remaining > 0:
            current_chunk_size = min(effective_chunk_size, bytes_remaining)
            if current_chunk_size == effective_chunk_size:
                yield self._chunk_data
            else:
                yield b"x" * current_chunk_size
            bytes_remaining -= current_chunk_size
            # Yield control to event loop
            await asyncio.sleep(0)

    async def download_to_file(self, key: str, path: str) -> None:
        """Download file to local path.
        
        Args:
            key: The blob key/path.
            path: Local file path to write to.
        """
        with open(path, "wb") as f:
            async for chunk in self.stream(key):
                f.write(chunk)
