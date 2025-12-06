import logging
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langserve import add_routes

from core.graph import create_graph
from core.ingestion import create_ingest_graph
from server.config import settings
from server.database import init_db
from server.health import get_health
from server.logging import init_logging
from server.model_gateway_routes import router as model_gateway_router
from server.routes import router as api_router
from server.routes import secure_router as api_secure_router

_otel_inited = False


def _init_otel():
    """
    Optional OpenTelemetry init (OTLP). No-op if dependencies or endpoint missing.
    """
    global _otel_inited
    if _otel_inited:
        return
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        service_name = os.environ.get("OTEL_SERVICE_NAME", "omnirag-api")
        resource = Resource.create({"service.name": service_name})
        ratio = float(
            os.environ.get(
                "OTEL_TRACE_SAMPLE_RATIO", getattr(settings, "otel_trace_sample_ratio", 1.0)
            )
            or 1.0
        )
        ratio = max(0.0, min(ratio, 1.0))
        provider = TracerProvider(resource=resource, sampler=TraceIdRatioBased(ratio))
        span_exporter = OTLPSpanExporter(
            endpoint=endpoint, insecure=bool(os.environ.get("OTEL_EXPORTER_OTLP_INSECURE"))
        )
        span_processor = BatchSpanProcessor(span_exporter)
        provider.add_span_processor(span_processor)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        _otel_inited = True
    except Exception:
        pass


app = FastAPI(
    title="OmniRAG Model Gateway",
    description="AI Model Gateway Configuration and Management API",
    version="1.0.0",
)
init_logging()
_init_otel()

# Startup configuration guards (prod-like)
_env = os.environ.get("APP_ENV", getattr(settings, "app_env", "dev")).lower()
if _env in {"prod", "production", "staging", "stage"}:
    # SECRET_KEY guard
    if not os.environ.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is required in production/staging")
    # Metrics guard
    if not (os.environ.get("METRICS_TOKEN") or getattr(settings, "metrics_token", None)):
        raise RuntimeError("METRICS_TOKEN is required in production/staging")
    allow_ips_env = os.environ.get("METRICS_ALLOW_IPS", "")
    allow_ips_cfg = getattr(settings, "metrics_allow_ips", []) or []
    allow = [x.strip() for x in allow_ips_env.split(",") if x.strip()] or allow_ips_cfg
    if not allow:
        raise RuntimeError("METRICS_ALLOW_IPS must be set in production/staging")
    # Vector backend guard
    if not getattr(settings, "force_vector_backend", None):
        raise RuntimeError("force_vector_backend must be set in production/staging")


# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    try:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            await init_db()
    except Exception:
        pass


rag_app = create_graph()
add_routes(app, rag_app, path="/rag")
ingest_app = create_ingest_graph()
add_routes(app, ingest_app, path="/ingest")

app.include_router(api_router, prefix="/api")
app.include_router(api_secure_router, prefix="/api")
app.include_router(model_gateway_router, prefix="/api")

# Optional Prometheus /metrics
try:
    import prometheus_client
except Exception:  # pragma: no cover - optional dependency
    prometheus_client = None

if prometheus_client:
    from fastapi import Header, Response

    @app.get("/metrics")
    async def metrics(
        authorization: str | None = Header(default=None), request: Request | None = None
    ):
        token = os.environ.get("METRICS_TOKEN") or getattr(settings, "metrics_token", None)
        if token:
            # Expect Authorization: Bearer <token>
            if not authorization or not authorization.lower().startswith("bearer "):
                return JSONResponse(status_code=401, content={"error": "unauthorized"})
            provided = authorization[7:]
            if provided != token:
                return JSONResponse(status_code=403, content={"error": "forbidden"})
        allow_ips_env = os.environ.get("METRICS_ALLOW_IPS")
        allow_ips_cfg = getattr(settings, "metrics_allow_ips", []) or []
        allow_ips = allow_ips_env.split(",") if allow_ips_env else allow_ips_cfg
        if allow_ips and request:
            ip = request.client.host if request.client else ""
            allow = {x.strip() for x in allow_ips if x and x.strip()}
            if allow and ip not in allow:
                return JSONResponse(status_code=403, content={"error": "forbidden"})
        data = prometheus_client.generate_latest()
        return Response(content=data, media_type="text/plain; version=0.0.4")


@app.get("/api/health")
async def health():
    return get_health()


_RATE_LIMIT_BUCKET: dict[str, list[float]] = {}
_REDIS_CLIENT: Any | None = None


def _get_redis():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    url = getattr(settings, "redis_url", None) or os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis

        _REDIS_CLIENT = redis.Redis.from_url(url)
    except Exception:
        _REDIS_CLIENT = None
    return _REDIS_CLIENT


async def _rate_limit(ip: str) -> bool:
    """返回是否被限流。支持 Redis，回退本地桶。"""
    per_min = int(getattr(settings, "rate_limit_per_minute", 60) or 60)
    if per_min <= 0:
        return False
    rds = _get_redis()
    now = int(time.time())
    if rds:
        try:
            key = f"ratelimit:{ip}:{now // 60}"
            # 自增并设置 TTL 70s
            n = rds.incr(key)
            if n == 1:
                rds.expire(key, 70)
            return n > per_min
        except Exception:
            pass
    # fallback: 进程内滑动窗口
    bucket = _RATE_LIMIT_BUCKET.setdefault(ip, [])
    bucket = [t for t in bucket if time.time() - t < 60.0]
    _RATE_LIMIT_BUCKET[ip] = bucket
    if len(bucket) >= per_min:
        return True
    bucket.append(time.time())
    return False


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    if getattr(settings, "rate_limit_enabled_resolved", False):
        try:
            ip = request.client.host if request.client else "unknown"
            limited = await _rate_limit(ip)
            if limited:
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Too Many Requests"},
                )
        except Exception:
            pass
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    logging.info(f"{rid} {request.method} {request.url}")
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = rid
    return resp


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", "-")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Invalid request",
            "details": exc.errors(),
            "request_id": rid,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "-")
    logging.exception(f"{rid} Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "request_id": rid,
        },
    )


_env = os.environ.get("APP_ENV", "dev").lower()
_default_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
cors_origins = getattr(settings, "cors_origins_resolved", []) or (
    _default_dev_origins if _env in {"dev", "local", "test"} else []
)
if _env in {"prod", "production", "staging", "stage"} and not cors_origins:
    raise RuntimeError("CORS origins must be explicitly configured in production/staging")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
