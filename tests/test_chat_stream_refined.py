import importlib.util
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "utils"))
from sse import find_event, parse_sse_text


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


def test_stream_events_and_final(monkeypatch):
    class DummyLLM:
        async def stream_chat(self, prompt: str, context: str = None):
            for ch in ["a", "b", "c"]:
                yield ch

        async def chat(self, prompt: str, context: str = None):
            return "abc"

    async def dummy_retrieve(state):
        return {
            "retrieved_chunks": [
                {
                    "id": "x",
                    "content": "c",
                    "page_num": 1,
                    "doc_id": "/tmp/a.pdf",
                    "chunk_index": 0,
                    "metadata": {},
                    "score": 0.9,
                    "rerank_score": None,
                }
            ]
        }

    monkeypatch.setattr(routes_mod, "LLMGateway", lambda: DummyLLM())
    monkeypatch.setattr(routes_mod, "retrieve_node", lambda s: dummy_retrieve(s))

    r = client.post("/api/chat/stream", json={"query": "hi", "top_k": 1})
    assert r.status_code == 200
    events = parse_sse_text(r.text)
    assert find_event(events, "phase") is not None
    final = find_event(events, "final")
    assert final is not None
