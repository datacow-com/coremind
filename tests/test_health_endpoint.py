import os
import importlib.util
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


health_mod = _load_module("server_health_local", "server/health.py")
app = FastAPI()

@app.get("/api/health")
async def health():
    return health_mod.get_health()

client = TestClient(app)


def test_health_endpoint_structure():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "app_up" in data
    assert "milvus_connected" in data
    assert "postgres_connected" in data
