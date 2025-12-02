import asyncio
import importlib.util
import os


def _load_module(name: str, rel_path: str):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, rel_path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


routes_mod = _load_module("server_routes_local", "server/routes.py")
get_providers = routes_mod.get_providers
set_providers = routes_mod.set_providers
test_provider = routes_mod.test_provider


def test_model_gateway_get_and_test():
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(get_providers())
    assert "config" in res
    assert "validations" in res
    # test provider validation
    tres = loop.run_until_complete(test_provider({"name": "openai"}))
    assert tres["status"] == "ok"


def test_model_gateway_set():
    loop = asyncio.get_event_loop()
    payload = {
        "bindings": {
            "parse": "gemini",
            "retrieve": "embedding",
            "chat": "openai",
            "rerank": "cross_encoder",
        },
        "providers": [
            {"name": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com"}
        ],
    }
    res = loop.run_until_complete(set_providers(payload))
    assert res["status"] == "ok"
