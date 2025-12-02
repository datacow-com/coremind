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


def test_system_status_structure():
    r = client.get("/api/system/status")
    assert r.status_code == 200
    data = r.json()
    assert "health" in data
    assert "config" in data
    assert "collections" in data
