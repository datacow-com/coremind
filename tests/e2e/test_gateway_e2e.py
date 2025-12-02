import os
import tempfile
import time

import httpx

BASE = os.getenv("E2E_BASE_URL", "http://localhost:3500")
API = f"{BASE}/api"


def _wait_health():
    for _ in range(60):
        try:
            r = httpx.get(f"{API}/health", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("health timeout")


def _get_token():
    r = httpx.post(f"{API}/auth/demo", timeout=10)
    assert r.status_code == 200
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token
    return token


def _auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_health():
    h = _wait_health()
    assert h.get("app_up") is True
    assert h.get("postgres_connected") is True


def test_dashboard_and_provider_flow():
    token = _get_token()
    headers = _auth_headers(token)
    r = httpx.get(f"{API}/models/dashboard/stats", headers=headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    payload = {
        "name": "qwen-plus",
        "stack": "cn",
        "category": "llm",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "priority": 1,
    }
    r = httpx.post(f"{API}/models/", headers=headers, json=payload, timeout=20)
    assert r.status_code in (200, 201)
    created = r.json()
    provider_id = created.get("id") or created.get("provider_id")
    assert provider_id
    r = httpx.get(f"{API}/models/?page=1&page_size=10", headers=headers, timeout=10)
    assert r.status_code == 200
    r = httpx.post(f"{API}/models/{provider_id}/test", headers=headers, json={}, timeout=30)
    assert r.status_code == 200
    test_res = r.json()
    assert isinstance(test_res, dict)


def test_env_versions_and_credentials():
    token = _get_token()
    headers = _auth_headers(token)
    r = httpx.post(
        f"{API}/models/environments/dev/versions",
        headers=headers,
        json={"config": {"llm": {"default": "qwen-plus"}}},
        timeout=20,
    )
    assert r.status_code in (200, 201)
    r = httpx.get(f"{API}/models/environments/dev/versions", headers=headers, timeout=10)
    assert r.status_code == 200
    versions = r.json()
    assert isinstance(versions, list)
    latest = versions[0]["version"] if versions else 1
    r = httpx.post(
        f"{API}/models/environments/dev/versions/{latest}/apply",
        headers=headers,
        params={"dry_run": True},
        timeout=10,
    )
    assert r.status_code == 200
    r = httpx.post(
        f"{API}/models/environments/dev/versions/{latest}/apply",
        headers=headers,
        params={"dry_run": False},
        timeout=10,
    )
    assert r.status_code == 200


def test_credentials_and_ingest():
    token = _get_token()
    headers = _auth_headers(token)
    payload = {
        "name": "qwen-plus",
        "stack": "cn",
        "category": "llm",
        "endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "priority": 1,
    }
    r = httpx.post(f"{API}/models/", headers=headers, json=payload, timeout=20)
    assert r.status_code in (200, 201)
    provider_id = r.json().get("id")
    assert provider_id
    cred_payload = {
        "auth_type": "api_key",
        "key_name": "dashscope",
        "rate_limit_rps": 10,
        "quota_limit": 1000,
        "quota_window": "daily",
    }
    r = httpx.post(
        f"{API}/models/{provider_id}/credentials/dev",
        headers=headers,
        json=cred_payload,
        timeout=20,
    )
    assert r.status_code in (200, 201)
    r = httpx.get(f"{API}/models/{provider_id}/credentials", headers=headers, timeout=10)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "OmniRAG E2E Test")
    doc.save(path)
    doc.close()
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f, "application/pdf")}
        r = httpx.post(f"{API}/ingest/pdf", files=files, timeout=30)
    os.remove(path)
    assert r.status_code == 200
    res = r.json()
    assert "md" in res and "md_path" in res
