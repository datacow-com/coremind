"""
Finalizer Node - Completes ingestion process with status updates.

Features:
- Final status update
- Cleanup temporary files
- SSE progress notification
- Metrics recording
"""

import os
from typing import Any

from core.state import IngestState

try:
    from core.utils.monitor import ingest_duration, ingest_requests
except ImportError:
    ingest_duration = None
    ingest_requests = None


class Finalizer:
    """
    Finalizes ingestion process with cleanup and notifications.
    """
    
    async def __call__(self, state: IngestState) -> IngestState:
        """Finalize ingestion process."""
        if ingest_duration:
            with ingest_duration.labels(stage="finalizer").time():
                return await self._finalize(state)
        return await self._finalize(state)
    
    async def _finalize(self, state: IngestState) -> IngestState:
        # Update final processing stage
        state["processing_stage"] = "completed"
        
        # Calculate final metrics
        chunks = state.get("chunks", [])
        error_log = state.get("error_log", [])
        quality_metrics = state.get("quality_metrics", {})
        
        # Build final progress report
        if "progress" not in state:
            state["progress"] = {}
        
        state["progress"]["status"] = "completed"
        state["progress"]["total_chunks"] = len(chunks)
        state["progress"]["error_count"] = len(error_log)
        state["progress"]["indexed_vector"] = state["progress"].get("indexed_vector", 0)
        state["progress"]["indexed_keyword"] = state["progress"].get("indexed_keyword", 0)
        
        # Quality summary
        if quality_metrics:
            state["progress"]["quality_original"] = quality_metrics.get("original_count", 0)
            state["progress"]["quality_filtered"] = quality_metrics.get("removed_count", 0)
        
        # Cleanup temporary files
        await self._cleanup_temp_files(state)
        
        # Record success metric
        if ingest_requests:
            if len(error_log) == 0:
                ingest_requests.labels(stage="finalizer", status="success").inc()
            else:
                ingest_requests.labels(stage="finalizer", status="with_errors").inc()
        
        # Notify SSE if available (placeholder for SSE integration)
        await self._notify_progress(state)
        
        return state
    
    async def _cleanup_temp_files(self, state: IngestState) -> None:
        """Clean up any temporary files created during processing."""
        temp_path = state.get("local_temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        
        # Clean up archive temp directory
        archive_temp = state.get("archive_temp_dir")
        if archive_temp and os.path.exists(archive_temp):
            try:
                import shutil
                shutil.rmtree(archive_temp, ignore_errors=True)
            except Exception:
                pass
    
    async def _notify_progress(self, state: IngestState) -> None:
        """
        Send SSE notification for progress update.
        This is a placeholder for SSE integration.
        """
        # TODO: Integrate with SSE notification system
        # Example:
        # from core.notifications import send_sse_event
        # await send_sse_event(
        #     channel=f"ingest_{state['task_id']}",
        #     event="completed",
        #     data=state["progress"]
        # )
        pass
