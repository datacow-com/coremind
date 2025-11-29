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


routes_mod = _load_module("server_routes_local", "server/routes.py")
auth_mod = _load_module("server_auth_local", "server/auth.py")
app = FastAPI()
app.include_router(routes_mod.secure_router, prefix="/api")
create_token = auth_mod.create_token


client = TestClient(app)


def test_providers_requires_auth():
    r = client.get("/api/models/providers")
    assert r.status_code == 401


def test_providers_with_token():
    tok = create_token("tester")
    r = client.get("/api/models/providers", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert "config" in data
