"""
Error Handler Node - Handles errors in ingestion pipeline.

Features:
- Error categorization
- Retry logic
- Fallback strategies
- Error reporting
"""

from typing import Any

from core.state import IngestState

try:
    from core.utils.monitor import ingest_requests
except ImportError:
    ingest_requests = None


class ErrorHandler:
    """
    Handles errors during ingestion and decides on recovery strategy.
    """
    
    # Maximum retry attempts
    MAX_RETRIES = 3
    
    # Recoverable error types
    RECOVERABLE_ERRORS = [
        "timeout",
        "rate_limit",
        "temporary",
        "connection",
    ]
    
    async def __call__(self, state: IngestState) -> IngestState:
        """Handle errors and determine next action."""
        error_log = state.get("error_log", [])
        retry_count = state.get("retry_count", 0)
        
        if not error_log:
            state["error_handled"] = True
            state["should_retry"] = False
            return state
        
        # Get latest error
        latest_error = error_log[-1] if error_log else {}
        error_stage = latest_error.get("stage", "unknown")
        error_message = str(latest_error.get("error", ""))
        
        # Categorize error
        error_type = self._categorize_error(error_message)
        latest_error["error_type"] = error_type
        
        # Determine if recoverable
        is_recoverable = error_type in self.RECOVERABLE_ERRORS
        can_retry = retry_count < self.MAX_RETRIES and is_recoverable
        
        if can_retry:
            state["retry_count"] = retry_count + 1
            state["should_retry"] = True
            state["processing_stage"] = self._get_retry_stage(error_stage)
        else:
            state["should_retry"] = False
            state["error_handled"] = True
            state["processing_stage"] = "failed"
            
            # Log permanent failure
            if "progress" not in state:
                state["progress"] = {}
            state["progress"]["failed"] = True
            state["progress"]["failure_reason"] = error_message[:500]
        
        # Track metrics
        if ingest_requests:
            status = "retry" if can_retry else "failed"
            ingest_requests.labels(stage=error_stage, status=status).inc()
        
        return state
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error type from message."""
        message_lower = error_message.lower()
        
        if "timeout" in message_lower:
            return "timeout"
        if "rate" in message_lower or "429" in message_lower:
            return "rate_limit"
        if "connection" in message_lower or "network" in message_lower:
            return "connection"
        if "temporary" in message_lower or "retry" in message_lower:
            return "temporary"
        if "permission" in message_lower or "auth" in message_lower:
            return "permission"
        if "not found" in message_lower or "404" in message_lower:
            return "not_found"
        if "invalid" in message_lower or "format" in message_lower:
            return "validation"
        
        return "unknown"
    
    def _get_retry_stage(self, failed_stage: str) -> str:
        """Determine which stage to retry from."""
        # Map failed stage to retry entry point
        retry_map = {
            "loader": "loader",
            "router": "loader",
            "cpu_parser": "router",
            "gpu_parser": "router",
            "chunker": "chunker",
            "embedder": "embedder",
            "indexer": "indexer",
        }
        return retry_map.get(failed_stage, "loader")
