import httpx


def test_me(api_url, auth_headers):
    r = httpx.get(f"{api_url}/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body.get("role") in ("system_admin", "config_admin", "read_only")
    assert isinstance(body.get("permissions", []), list)


def test_bindings_flow(api_url, auth_headers, provider_id):
    # create task binding using legacy fields
    payload = {
        "task_id": "chat",
        "task_name": "chat-default",
        "model_id": provider_id,
        "priority": 1,
        "fallback_config": {},
        "environment": "dev",
    }
    r = httpx.post(f"{api_url}/models/bindings", headers=auth_headers, json=payload, timeout=20)
    assert r.status_code in (200, 201)
    # query binding
    r = httpx.get(f"{api_url}/models/bindings/chat-default/dev", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
