import os
import time
import httpx
import pytest

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3500")
API = f"{BASE}/api"

@pytest.fixture(scope="session")
def base_url():
    return BASE

@pytest.fixture(scope="session")
def api_url():
    return API

@pytest.fixture(scope="session")
def wait_health(api_url):
    for _ in range(60):
        try:
            r = httpx.get(f"{api_url}/health", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("health timeout")

@pytest.fixture(scope="session")
def token(api_url, wait_health):
    r = httpx.post(f"{api_url}/auth/demo", timeout=10)
    assert r.status_code == 200
    data = r.json()
    return data.get("access_token") or data.get("token")

@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="session")
def provider_id(api_url, auth_headers):
    payload = {
        "name": "qwen-plus",
        "stack": "cn",
        "category": "llm",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "priority": 1,
    }
    r = httpx.post(f"{api_url}/models/", headers=auth_headers, json=payload, timeout=20)
    assert r.status_code in (200, 201)
    return r.json().get("id")
