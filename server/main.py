from fastapi import FastAPI
from langserve import add_routes
from core.graph import create_graph
from server.routes import router as api_router
from server.routes import secure_router as api_secure_router

app = FastAPI()

rag_app = create_graph()
add_routes(app, rag_app, path="/rag")

app.include_router(api_router, prefix="/api")
app.include_router(api_secure_router, prefix="/api")
