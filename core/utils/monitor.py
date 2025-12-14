"""
OmniRAG Observability Module

Provides:
- Prometheus metrics for monitoring
- OpenTelemetry tracing for distributed tracing
- Helper functions for instrumentation

P2 Fix: Enhanced observability with more granular metrics and tracing.
P1 Fix: Lazy import of gRPC exporter to avoid mutex lock on import.
"""

import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TYPE_CHECKING

# Lazy imports for OpenTelemetry to avoid gRPC mutex lock on module import
# Only import types for type checking
if TYPE_CHECKING:
    from opentelemetry.trace import Span

from prometheus_client import Counter, Histogram, Gauge, Summary

# --- Prometheus Metrics ---

# Ingestion Metrics
ingest_requests = Counter(
    'rag_ingest_requests_total', 
    'Total ingest requests', 
    ['stage', 'status']
)

ingest_duration = Histogram(
    'rag_ingest_duration_seconds', 
    'Ingest duration seconds', 
    ['stage'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300]
)

ingest_chunks_total = Counter(
    'rag_ingest_chunks_total',
    'Total chunks ingested',
    ['kb_name', 'channel_id', 'status']
)

ingest_file_size = Histogram(
    'rag_ingest_file_size_bytes',
    'Ingested file sizes',
    ['file_type'],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600, 1073741824]  # 1KB to 1GB
)

# Queue Metrics
queue_depth = Gauge(
    'rag_queue_depth', 
    'Queue depth', 
    ['queue_name']
)

# Retrieval Metrics
retrieval_latency = Histogram(
    'rag_retrieval_latency_seconds', 
    'Retrieval latency seconds',
    buckets=[0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

retrieval_requests = Counter(
    'rag_retrieval_requests_total',
    'Total retrieval requests',
    ['status']
)

retrieval_results_count = Histogram(
    'rag_retrieval_results_count',
    'Number of results returned per query',
    ['kb_name', 'intent_type'],
    buckets=[0, 1, 5, 10, 20, 50, 100]
)

# P2 Fix: Semantic Cache Metrics
semantic_cache_hits = Counter(
    'rag_semantic_cache_hits_total',
    'Semantic cache hits',
    ['channel_id']
)

semantic_cache_misses = Counter(
    'rag_semantic_cache_misses_total',
    'Semantic cache misses',
    ['channel_id']
)

# P2 Fix: Reranker Metrics
reranker_duration = Histogram(
    'rag_reranker_duration_seconds',
    'Reranker processing duration',
    ['provider'],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5]
)

# P2 Fix: LLM Metrics
llm_requests = Counter(
    'rag_llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'status']
)

llm_latency = Histogram(
    'rag_llm_latency_seconds',
    'LLM request latency',
    ['provider', 'model'],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

llm_tokens = Counter(
    'rag_llm_tokens_total',
    'Total LLM tokens used',
    ['provider', 'model', 'type']  # type: input/output
)

# P2 Fix: Algorithm Metrics (RAPTOR/GraphRAG)
algorithm_duration = Histogram(
    'rag_algorithm_duration_seconds',
    'Algorithm processing duration',
    ['algorithm', 'kb_name'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800]
)

algorithm_chunks_processed = Counter(
    'rag_algorithm_chunks_processed_total',
    'Chunks processed by algorithms',
    ['algorithm', 'kb_name']
)

# --- OpenTelemetry Setup (Lazy) ---

_tracer = None
_otel_initialized = False


def _get_tracer():
    """Lazily get or create tracer to avoid gRPC mutex lock on import."""
    global _tracer, _otel_initialized
    
    if _tracer is not None:
        return _tracer
    
    try:
        from opentelemetry import trace
        
        if not _otel_initialized:
            _otel_initialized = True
            # Only setup if ENABLE_OTEL is true
            if os.environ.get("ENABLE_OTEL", "false").lower() == "true":
                setup_monitor()
        
        _tracer = trace.get_tracer("omnirag.core")
        return _tracer
    except ImportError:
        # OpenTelemetry not installed, return a no-op tracer
        return _NoOpTracer()


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""
    
    @contextmanager
    def start_as_current_span(self, name, kind=None):
        yield _NoOpSpan()


class _NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""
    
    def set_attribute(self, key, value):
        pass
    
    def set_status(self, status):
        pass
    
    def record_exception(self, exception):
        pass


def setup_monitor():
    """Initialize OpenTelemetry tracing. Called lazily when needed."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
        service_name = os.environ.get("OTEL_SERVICE_NAME", "omnirag-core")
        
        resource = Resource.create({
            "service.name": service_name,
            "service.version": os.environ.get("SERVICE_VERSION", "1.0.0"),
        })
        provider = TracerProvider(resource=resource)
        
        if os.environ.get("ENABLE_OTEL", "false").lower() == "true":
            # Only import gRPC exporter when actually needed
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
            provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
    except ImportError:
        pass


# Backward compatible tracer property
class _LazyTracer:
    """Proxy for lazy tracer access."""
    
    def __getattr__(self, name):
        return getattr(_get_tracer(), name)
    
    def start_as_current_span(self, *args, **kwargs):
        return _get_tracer().start_as_current_span(*args, **kwargs)


tracer = _LazyTracer()


# --- P2 Fix: Tracing Helpers ---

@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: Any = None,  # SpanKind.INTERNAL, lazy loaded
):
    """
    Context manager for creating traced spans.
    
    Usage:
        with create_span("my_operation", {"key": "value"}) as span:
            # do work
            span.set_attribute("result", "success")
    """
    # Lazy import SpanKind
    if kind is None:
        try:
            from opentelemetry.trace import SpanKind
            kind = SpanKind.INTERNAL
        except ImportError:
            kind = None
    
    with tracer.start_as_current_span(name, kind=kind) as span:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool)) else v)
        try:
            yield span
        except Exception as e:
            try:
                from opentelemetry.trace import Status, StatusCode
                span.set_status(Status(StatusCode.ERROR, str(e)))
            except ImportError:
                pass
            span.record_exception(e)
            raise


def trace_async(name: str = None, attributes: dict[str, Any] | None = None):
    """
    Decorator for tracing async functions.
    
    Usage:
        @trace_async("my_operation")
        async def my_func():
            pass
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                result = await func(*args, **kwargs)
                return result
        return wrapper
    return decorator


def trace_sync(name: str = None, attributes: dict[str, Any] | None = None):
    """
    Decorator for tracing sync functions.
    
    Usage:
        @trace_sync("my_operation")
        def my_func():
            pass
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            with create_span(span_name, attributes) as span:
                result = func(*args, **kwargs)
                return result
        return wrapper
    return decorator


def record_retrieval_metrics(
    kb_name: str,
    intent_type: str,
    results_count: int,
    latency_seconds: float,
    cache_hit: bool = False,
    channel_id: str = "",
):
    """Helper to record retrieval metrics."""
    retrieval_results_count.labels(kb_name=kb_name, intent_type=intent_type).observe(results_count)
    retrieval_latency.observe(latency_seconds)
    retrieval_requests.labels(status="success" if results_count > 0 else "no_results").inc()
    
    if cache_hit:
        semantic_cache_hits.labels(channel_id=channel_id).inc()
    else:
        semantic_cache_misses.labels(channel_id=channel_id).inc()


def record_ingest_metrics(
    stage: str,
    status: str,
    kb_name: str = "",
    channel_id: str = "",
    chunks_count: int = 0,
    file_size: int = 0,
    file_type: str = "",
):
    """Helper to record ingestion metrics."""
    ingest_requests.labels(stage=stage, status=status).inc()
    
    if chunks_count > 0:
        ingest_chunks_total.labels(
            kb_name=kb_name, 
            channel_id=channel_id, 
            status=status
        ).inc(chunks_count)
    
    if file_size > 0 and file_type:
        ingest_file_size.labels(file_type=file_type).observe(file_size)

