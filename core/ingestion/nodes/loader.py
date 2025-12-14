"""
Loader Node - Load file content from blob storage with lazy loading support.

Handles:
- Archive expansion (ZIP/TAR)
- Large file detection and lazy loading
- Memory-efficient processing for files > 100MB
"""

import os
from typing import Any

from core.state import IngestState
from core.storage.blob_store import get_blob_store
from core.utils.monitor import ingest_duration, ingest_requests

# Threshold for lazy loading (100MB)
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
# Maximum file size to load entirely into memory (500MB)
MAX_MEMORY_FILE_SIZE = 500 * 1024 * 1024  # 500MB
# Unknown size sentinel
UNKNOWN_SIZE = -1


class LoaderNode:
    """Document loader with large file handling."""

    async def __call__(self, state: IngestState) -> IngestState:
        """
        Load file content from blob storage or local path.
        Handle archive expansion or lazy loading for large files.
        """
        with ingest_duration.labels(stage="loader").time():
            try:
                file_path = state["file_path"]
                file_type = state["file_type"]
                blob_store = get_blob_store()

                # Update stage
                state["processing_stage"] = "parse"

                # Check file exists
                if not await blob_store.exists(file_path):
                    raise FileNotFoundError(f"File {file_path} not found in blob store")

                # Get file size for large file handling
                file_size = await self._get_file_size(blob_store, file_path)
                state["progress"] = state.get("progress", {})
                state["progress"]["file_size"] = file_size

                # Handle archives (ZIP/TAR) - dispatch to sub-processor
                if file_type in ["zip", "tar", "tar.gz", "tgz"]:
                    return await self._handle_archive(state, blob_store, file_path, file_type)

                # Large file handling
                if file_size == UNKNOWN_SIZE:
                    # Unknown size: safer to require lazy handling
                    state["raw_content"] = None
                    state["lazy_load"] = True
                    state["lazy_load_path"] = file_path
                    state["file_size"] = UNKNOWN_SIZE
                    state["error_log"].append({
                        "stage": "loader",
                        "warning": "Unknown file size, using streaming/lazy mode"
                    })

                elif file_size > MAX_MEMORY_FILE_SIZE:
                    # Too large to process - mark as streaming required
                    state["raw_content"] = None
                    state["lazy_load"] = True
                    state["lazy_load_path"] = file_path
                    state["file_size"] = file_size
                    state["error_log"].append({
                        "stage": "loader",
                        "warning": f"File too large ({file_size / 1024 / 1024:.1f}MB), using streaming mode"
                    })

                elif file_size > LARGE_FILE_THRESHOLD:
                    # Large but manageable - download to temp and let parser stream
                    state["raw_content"] = None
                    state["lazy_load"] = True
                    state["lazy_load_path"] = file_path
                    state["file_size"] = file_size
                    # Download to local temp for streaming access
                    temp_path = await self._download_to_temp(blob_store, file_path)
                    state["local_temp_path"] = temp_path

                else:
                    # Small file - read entirely into memory
                    content = await blob_store.get(file_path)
                    state["raw_content"] = content
                    state["lazy_load"] = False
                    state["file_size"] = len(content) if content else 0

                ingest_requests.labels(stage="loader", status="success").inc()
                return state

            except Exception as e:
                state["error_log"].append({"stage": "loader", "error": str(e)})
                ingest_requests.labels(stage="loader", status="error").inc()
                return state

    async def _get_file_size(self, blob_store: Any, file_path: str) -> int:
        """Get file size from blob store. Returns UNKNOWN_SIZE on failure."""
        try:
            # Try to use head/stat method if available
            if hasattr(blob_store, "head"):
                info = await blob_store.head(file_path)
                return info.get("size", UNKNOWN_SIZE)
            elif hasattr(blob_store, "stat"):
                info = await blob_store.stat(file_path)
                return info.get("size", UNKNOWN_SIZE)
            elif hasattr(blob_store, "get_size"):
                return await blob_store.get_size(file_path)

            # Fallback: check local file if it's a local path
            if os.path.exists(file_path):
                return os.path.getsize(file_path)

            # Last resort: unknown size
            return UNKNOWN_SIZE

        except Exception:
            return UNKNOWN_SIZE

    async def _download_to_temp(self, blob_store: Any, file_path: str) -> str:
        """Download large file to temporary location for streaming."""
        import tempfile
        import aiofiles

        # Create temp file with same extension
        ext = os.path.splitext(file_path)[1]
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)

        try:
            # Stream download if available
            if hasattr(blob_store, "download_to_file"):
                await blob_store.download_to_file(file_path, temp_path)
            elif hasattr(blob_store, "stream"):
                async with aiofiles.open(temp_path, "wb") as f:
                    async for chunk in blob_store.stream(file_path):
                        await f.write(chunk)
            else:
                # P1 Fix: Reject large files if blob store doesn't support streaming
                # This prevents OOM from loading entire large files into memory
                file_size = await self._get_file_size(blob_store, file_path)
                if file_size > LARGE_FILE_THRESHOLD:
                    raise RuntimeError(
                        f"Blob store does not support streaming downloads. "
                        f"Cannot safely process file larger than {LARGE_FILE_THRESHOLD / 1024 / 1024:.0f}MB. "
                        f"File size: {file_size / 1024 / 1024:.1f}MB. "
                        f"Please upgrade blob store to support streaming or reduce file size."
                    )
                # Small files can still use full download
                content = await blob_store.get(file_path)
                async with aiofiles.open(temp_path, "wb") as f:
                    await f.write(content)

            return temp_path

        except Exception as e:
            # Clean up on failure
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise RuntimeError(f"Failed to download file for streaming: {e}")

    async def _handle_archive(
        self, state: IngestState, blob_store: Any, file_path: str, file_type: str
    ) -> IngestState:
        """Handle archive files (ZIP/TAR) - extract and create sub-tasks."""
        import zipfile
        import tarfile
        import tempfile
        import shutil
        from pathlib import Path

        # ZIP bomb protection limits
        MAX_ARCHIVE_FILES = 100  # Maximum number of files in archive
        MAX_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500MB max uncompressed size

        # Download archive to temp
        temp_dir = tempfile.mkdtemp(prefix="omnirag_archive_")

        try:
            # Download archive
            archive_content = await blob_store.get(file_path)
            archive_path = os.path.join(temp_dir, os.path.basename(file_path))
            with open(archive_path, "wb") as f:
                f.write(archive_content)

            # ZIP bomb protection: check before extraction
            if file_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    file_list = zf.namelist()
                    file_count = len(file_list)
                    
                    # Check file count
                    if file_count > MAX_ARCHIVE_FILES:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        state["error_log"].append({
                            "stage": "loader",
                            "error": f"zip_bomb_protection: Archive contains {file_count} files, "
                                     f"exceeds limit of {MAX_ARCHIVE_FILES}. "
                                     f"Too many files in archive."
                        })
                        state["processing_stage"] = "error"
                        return state
                    
                    # Check uncompressed size
                    total_uncompressed = sum(info.file_size for info in zf.infolist())
                    if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        state["error_log"].append({
                            "stage": "loader",
                            "error": f"zip_bomb_protection: Archive uncompressed size "
                                     f"({total_uncompressed / 1024 / 1024:.1f}MB) "
                                     f"exceeds limit of {MAX_UNCOMPRESSED_SIZE / 1024 / 1024:.0f}MB. "
                                     f"Archive too large when extracted."
                        })
                        state["processing_stage"] = "error"
                        return state

            elif file_type in ["tar", "tar.gz", "tgz"]:
                mode = "r:gz" if file_type in ["tar.gz", "tgz"] else "r"
                with tarfile.open(archive_path, mode) as tf:
                    members = tf.getmembers()
                    file_count = len(members)
                    
                    # Check file count
                    if file_count > MAX_ARCHIVE_FILES:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        state["error_log"].append({
                            "stage": "loader",
                            "error": f"zip_bomb_protection: Archive contains {file_count} files, "
                                     f"exceeds limit of {MAX_ARCHIVE_FILES}. "
                                     f"Too many files in archive."
                        })
                        state["processing_stage"] = "error"
                        return state
                    
                    # Check uncompressed size
                    total_uncompressed = sum(m.size for m in members if m.isfile())
                    if total_uncompressed > MAX_UNCOMPRESSED_SIZE:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        state["error_log"].append({
                            "stage": "loader",
                            "error": f"zip_bomb_protection: Archive uncompressed size "
                                     f"({total_uncompressed / 1024 / 1024:.1f}MB) "
                                     f"exceeds limit of {MAX_UNCOMPRESSED_SIZE / 1024 / 1024:.0f}MB. "
                                     f"Archive too large when extracted."
                        })
                        state["processing_stage"] = "error"
                        return state

            # Extract archive (passed ZIP bomb checks)
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir)

            if file_type == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(extract_dir)
            elif file_type in ["tar", "tar.gz", "tgz"]:
                mode = "r:gz" if file_type in ["tar.gz", "tgz"] else "r"
                with tarfile.open(archive_path, mode) as tf:
                    tf.extractall(extract_dir)

            # Collect extracted files
            extracted_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, extract_dir)
                    extracted_files.append({
                        "path": full_path,
                        "relative_path": rel_path,
                        "size": os.path.getsize(full_path),
                    })

            # Store extracted info in state for sub-graph processing
            state["archive_extracted"] = True
            state["archive_files"] = extracted_files
            state["archive_temp_dir"] = temp_dir
            state["raw_content"] = None  # Don't load archive itself

            # First file can be processed inline if small
            if extracted_files:
                first_file = extracted_files[0]
                if first_file["size"] < LARGE_FILE_THRESHOLD:
                    with open(first_file["path"], "rb") as f:
                        state["raw_content"] = f.read()
                    state["file_path"] = first_file["path"]

        except Exception as e:
            # Clean up on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            state["error_log"].append({
                "stage": "loader",
                "error": f"Archive extraction failed: {e}"
            })

        return state
