"""
OpenTelemetry Tracing Utilities for OmniRAG.

Provides decorators and utilities for adding spans to nodes.
"""

import functools
from typing import Any, Callable, TypeVar

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode
    
    tracer = trace.get_tracer("omnirag")
    OTEL_AVAILABLE = True
except ImportError:
    tracer = None
    OTEL_AVAILABLE = False
    StatusCode = None


T = TypeVar("T")


def traced_node(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
):
    """
    Decorator to add OpenTelemetry tracing to a node.
    
    Usage:
        @traced_node("loader", {"component": "ingestion"})
        async def __call__(self, state):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if not OTEL_AVAILABLE:
            return func
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            span_name = name or func.__name__
            
            with tracer.start_as_current_span(span_name) as span:
                # Add default attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Try to extract state info
                state = args[1] if len(args) > 1 else kwargs.get("state", {})
                if isinstance(state, dict):
                    if "task_id" in state:
                        span.set_attribute("task_id", state["task_id"])
                    if "file_path" in state:
                        span.set_attribute("file_path", str(state["file_path"])[:200])
                    if "file_type" in state:
                        span.set_attribute("file_type", state["file_type"])
                    if "kb_name" in state:
                        span.set_attribute("kb_name", state["kb_name"])
                    if "channel_id" in state:
                        span.set_attribute("channel_id", state["channel_id"])
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Add result metrics
                    if isinstance(result, dict):
                        if "chunks" in result:
                            span.set_attribute("chunk_count", len(result.get("chunks", [])))
                        if "error_log" in result and result["error_log"]:
                            span.set_attribute("error_count", len(result["error_log"]))
                    
                    span.set_status(StatusCode.OK)
                    return result
                    
                except Exception as e:
                    span.set_status(StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            span_name = name or func.__name__
            
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """
    Add attributes to the current span.
    
    Usage:
        add_span_attributes({"page_count": 10, "file_size": 1024})
    """
    if not OTEL_AVAILABLE:
        return
    
    span = trace.get_current_span()
    if span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)


def record_exception(exception: Exception, attributes: dict[str, Any] | None = None) -> None:
    """
    Record an exception to the current span.
    """
    if not OTEL_AVAILABLE:
        return
    
    span = trace.get_current_span()
    if span:
        span.record_exception(exception)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)


class SpanContext:
    """
    Context manager for creating spans.
    
    Usage:
        with SpanContext("process_page", {"page_num": 1}) as span:
            # do work
            span.set_attribute("chars_extracted", 1000)
    """
    
    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self.attributes = attributes or {}
        self._span = None
        self._token = None
    
    def __enter__(self):
        if not OTEL_AVAILABLE:
            return self
        
        self._span = tracer.start_span(self.name)
        for key, value in self.attributes.items():
            if value is not None:
                self._span.set_attribute(key, value)
        
        self._token = trace.use_span(self._span)
        self._token.__enter__()
        return self._span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not OTEL_AVAILABLE or not self._span:
            return False
        
        if exc_type is not None:
            self._span.set_status(StatusCode.ERROR, str(exc_val))
            self._span.record_exception(exc_val)
        else:
            self._span.set_status(StatusCode.OK)
        
        self._token.__exit__(exc_type, exc_val, exc_tb)
        self._span.end()
        return False
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)
