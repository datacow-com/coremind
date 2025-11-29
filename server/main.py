from fastapi import FastAPI
from langserve import add_routes
from core.graph import create_graph
from server.routes import router as api_router
from server.routes import secure_router as api_secure_router
from server.config import settings
from server.health import get_health
from server.logging import init_logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uuid
import logging

app = FastAPI()
init_logging()

rag_app = create_graph()
add_routes(app, rag_app, path="/rag")

app.include_router(api_router, prefix="/api")
app.include_router(api_secure_router, prefix="/api")


@app.get("/api/health")
async def health():
    return get_health()


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())
    request.state.request_id = rid
    logging.info(f"{rid} {request.method} {request.url}")
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = rid
    return resp


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "request_id", "-")
    return JSONResponse(status_code=422, content={
        "error": "validation_error",
        "message": "Invalid request",
        "details": exc.errors(),
        "request_id": rid,
    })


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "-")
    logging.exception(f"{rid} Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={
        "error": "internal_error",
        "message": "Unexpected server error",
        "request_id": rid,
    })
