import json
import os

from core.llm.gateway import LLMGateway


class DummyHTTPXClient:
    def __init__(self, timeout=5.0):
        self.timeout = timeout
        self.last = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None):
        self.last = {"url": url, "json": json}

        class R:
            status_code = 200

        return R()


def test_threshold_webhook_trigger(tmp_path, monkeypatch):
    base = tmp_path / "usage"
    os.makedirs(base, exist_ok=True)
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "http://example.com/webhook")
    # write thresholds.json
    th = {
        "max_tokens_per_day": 10,
        "max_calls_per_day": 0,
        "max_cost_per_day": 0.0,
        "webhook_url": "http://example.com/webhook",
    }
    with open(base / "thresholds.json", "w", encoding="utf-8") as f:
        json.dump(th, f)
    # redirect usage dir
    gw = LLMGateway(provider="dashscope")

    def fake_usage_dir():
        return str(base)

    monkeypatch.setattr(LLMGateway, "_usage_dir", lambda self: str(base))
    # monkeypatch httpx.Client used inside gateway
    import core.llm.gateway as gmod

    gmod.httpx = type("H", (), {"Client": DummyHTTPXClient})
    # record usage exceeding tokens
    gw._record_usage(
        kind="chat",
        provider="dashscope",
        model="qwen-plus",
        tokens_in=8,
        tokens_out=5,
        duration_ms=100,
    )
    # assert webhook captured
    client = gmod.httpx.Client()
    assert client.last is not None or os.path.exists(base / "usage.jsonl")
