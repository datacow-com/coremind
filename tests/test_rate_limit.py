import importlib.util
import os

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
main_mod = _load_module("server_main_local", "server/main.py")
app = main_mod.app
app.include_router(routes_mod.router, prefix="/api")
client = TestClient(app)


def test_rate_limit_returns_429(monkeypatch):
    from server import config as cfg

    monkeypatch.setattr(cfg.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(cfg.settings, "rate_limit_per_minute", 1)
    r1 = client.get("/api/health")
    assert r1.status_code in (200, 429)
    r2 = client.get("/api/health")
    assert r2.status_code == 429
