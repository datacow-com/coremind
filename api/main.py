from fastapi import FastAPI
from langserve import add_routes
from core.graph import create_graph
from api.routes import router as api_router

app = FastAPI()

rag_app = create_graph()
add_routes(app, rag_app, path="/rag")

app.include_router(api_router, prefix="/api")
