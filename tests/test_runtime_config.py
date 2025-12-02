import importlib.util
import os

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(name: str, rel_path: str):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


routes_mod = _load_module("server_routes_local", "server/routes.py")
app = FastAPI()
app.include_router(routes_mod.router, prefix="/api")
client = TestClient(app)


def test_runtime_config_has_keys():
    r = client.get("/api/config/runtime")
    assert r.status_code == 200
    data = r.json()
    for k in [
        "llm_provider",
        "vision_provider",
        "web_search_provider",
        "chat_temperature",
        "vector_weight",
        "keyword_weight",
        "top_k_default",
        "rrf_k",
        "reranker_filter_threshold",
        "grade_threshold",
        "hallucination_threshold",
        "uploads_dir",
        "milvus_uri",
        "web_search_timeout",
    ]:
        assert k in data
