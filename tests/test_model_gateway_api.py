import asyncio
from api.routes import get_providers, set_providers, test_provider


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
        "bindings": {"parse": "gemini", "retrieve": "embedding", "chat": "openai", "rerank": "cross_encoder"},
        "providers": [{"name": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com"}],
    }
    res = loop.run_until_complete(set_providers(payload))
    assert res["status"] == "ok"

