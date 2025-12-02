import logging
import os
import time
import uuid

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

app = FastAPI(
    title="OmniRAG Model Gateway",
    description="AI Model Gateway Configuration and Management API",
    version="1.0.0",
)
init_logging()


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


@app.get("/api/health")
async def health():
    return get_health()


_RATE_LIMIT_BUCKET: dict[str, list[float]] = {}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    if getattr(settings, "rate_limit_enabled", False):
        try:
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            bucket = _RATE_LIMIT_BUCKET.setdefault(ip, [])
            bucket = [t for t in bucket if now - t < 60.0]
            _RATE_LIMIT_BUCKET[ip] = bucket
            if len(bucket) >= int(getattr(settings, "rate_limit_per_minute", 60)):
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Too Many Requests"},
                )
            bucket.append(now)
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
            "message": "Unexpected server error",
            "request_id": rid,
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "cors_origins", []) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
