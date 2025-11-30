import os
import importlib.util
from fastapi import FastAPI
from fastapi.testclient import TestClient
import types


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


def test_vector_collections_endpoint():
    r = client.get("/api/vector-store/collections")
    assert r.status_code == 200
    data = r.json()
    assert "collections" in data
    assert isinstance(data["collections"], list)
    if data["collections"]:
        c = data["collections"][0]
        for k in ["name", "document_count", "chunk_count", "embedding_dimension", "distance_metric"]:
            assert k in c


def test_vector_search_endpoint_structure(monkeypatch):
    class DummyEmbedder:
        def __init__(self, dim: int = 256):
            self.dim = dim
        def embed(self, text: str):
            import numpy as np
            return np.zeros(self.dim, dtype=np.float32)

    def fake_search(qvec, top_k=10):
        return [({
            "id": "docA-p1-chunk-0",
            "content": "hello world",
            "page_num": 1,
            "doc_id": "/tmp/docA.pdf",
            "chunk_index": 0,
            "metadata": {},
        }, 0.99)]

    # patch Embedder and index search in the loaded module namespace
    monkeypatch.setattr(routes_mod, "Embedder", DummyEmbedder)
    monkeypatch.setattr(routes_mod, "index_search", fake_search)

    r = client.post("/api/vector-store/search", json={"query": "test", "top_k": 1})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    if data["results"]:
        it = data["results"][0]
        for k in ["chunk_id", "content", "score", "document_name", "page_number"]:
            assert k in it
