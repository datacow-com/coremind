import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from prometheus_client import Counter, Histogram, Gauge

# --- Prometheus Metrics ---

ingest_requests = Counter(
    'rag_ingest_requests_total', 
    'Total ingest requests', 
    ['stage', 'status']
)

ingest_duration = Histogram(
    'rag_ingest_duration_seconds', 
    'Ingest duration seconds', 
    ['stage']
)

queue_depth = Gauge(
    'rag_queue_depth', 
    'Queue depth', 
    ['queue_name']
)

retrieval_latency = Histogram(
    'rag_retrieval_latency_seconds', 
    'Retrieval latency seconds'
)

retrieval_requests = Counter(
    'rag_retrieval_requests_total',
    'Total retrieval requests',
    ['status']
)

# --- OpenTelemetry Setup ---

def setup_monitor():
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    service_name = os.environ.get("OTEL_SERVICE_NAME", "omnirag-core")
    
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    if os.environ.get("ENABLE_OTEL", "false").lower() == "true":
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        provider.add_span_processor(processor)
    
    trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

