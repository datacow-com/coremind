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
app = FastAPI()
app.include_router(routes_mod.router, prefix="/api")
client = TestClient(app)


def test_chat_stream_basic(monkeypatch):
    class DummyLLM:
        async def stream_chat(self, prompt: str, context: str = None):
            for ch in ["Hello ", "World"]:
                yield ch
        async def chat(self, prompt: str, context: str = None):
            return "Hello World"

    async def dummy_retrieve(state):
        return {"retrieved_chunks": [{"id": "x", "content": "c", "page_num": 1, "doc_id": "/tmp/a.pdf", "chunk_index": 0, "metadata": {}, "score": 0.9, "rerank_score": None}]}

    # patch LLM and retrieve node
    monkeypatch.setattr(routes_mod, "LLMGateway", lambda: DummyLLM())
    monkeypatch.setattr(routes_mod, "retrieve_node", lambda s: dummy_retrieve(s))

    r = client.post("/api/chat/stream", json={"query": "hi", "top_k": 1})
    assert r.status_code == 200
    # stream should contain data chunks
    text = r.text
    assert "data:" in text
    assert "phase" in text
    assert "answer" in text or "final" in text
