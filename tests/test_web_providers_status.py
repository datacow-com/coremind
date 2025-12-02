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


def test_web_providers_status_structure():
    r = client.get("/api/web/providers/status")
    assert r.status_code == 200
    data = r.json()
    assert "current_provider" in data
    assert "providers" in data
    providers = data["providers"]
    for name in ["tavily", "serper", "bocha", "duckduckgo"]:
        assert name in providers
        assert "configured" in providers[name]


def test_web_providers_select_changes_current():
    r = client.post("/api/web/providers/select", json={"provider": "duckduckgo"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    s = client.get("/api/web/providers/status").json()
    assert s.get("current_provider") == "duckduckgo"
