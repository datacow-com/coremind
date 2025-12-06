import asyncio
import json
import time

import httpx


async def main():
    from server.main import app

    out = {}
    async with httpx.AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:

        async def call(name: str, method: str, url: str, **kwargs):
            t0 = time.perf_counter()
            try:
                r = await client.request(method, url, **kwargs)
                dur = int((time.perf_counter() - t0) * 1000)
                try:
                    data = r.json()
                except Exception:
                    data = r.text
                out[name] = {"status": r.status_code, "duration_ms": dur, "data": data}
            except Exception as e:
                dur = int((time.perf_counter() - t0) * 1000)
                out[name] = {"error": str(e), "duration_ms": dur}

        await call("health", "GET", "/api/health")
        await call("system_status", "GET", "/api/system/status")
        await call("embedding_models", "GET", "/api/embedding/models")

        await call(
            "kb_create",
            "POST",
            "/api/kb/create",
            json={"name": "kb_test_api", "stack": "cn", "vector_backend": "local"},
        )
        await call("kb_get_config", "GET", "/api/kb/kb_test_api/config")
        await call(
            "kb_update",
            "POST",
            "/api/kb/kb_test_api/config",
            json={
                "embedding_model": "BAAI/bge-m3",
                "top_k_default": 7,
                "candidate_k": 40,
                "vector_weight": 0.7,
                "keyword_weight": 0.3,
                "reranker_filter_threshold": 0.25,
                "rrf_k": 70,
                "web_search_enabled": False,
            },
        )

        await call(
            "debug_embed",
            "POST",
            "/api/debug/embed",
            json={"text": "测试默认嵌入", "dim": 256},
        )
        await call(
            "debug_embed_kb",
            "POST",
            "/api/debug/embed/kb",
            json={"kb_name": "kb_test_api", "text": "测试 KB 嵌入", "dim": 256},
        )
        await call(
            "vector_search",
            "POST",
            "/api/vector-store/search",
            json={"query": "测试", "top_k": 3, "kb_name": "kb_test_api"},
        )
        await call("kb_reset", "POST", "/api/kb/kb_test_api/config/reset")
        await call("kb_config_after_reset", "GET", "/api/kb/kb_test_api/config")

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
