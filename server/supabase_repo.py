import os
from typing import Any

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


class SupabaseRepo:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError("Supabase env missing")
        self.base = SUPABASE_URL.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def _get(self, path: str, params: dict[str, Any]) -> tuple[int, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(self.base + path, headers=self.headers, params=params)
            return r.status_code, r.json()

    async def _post(self, path: str, json: Any) -> tuple[int, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(self.base + path, headers=self.headers, json=json)
            return r.status_code, r.json()

    async def _patch(self, path: str, json: Any, params: dict[str, Any]) -> tuple[int, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.patch(self.base + path, headers=self.headers, params=params, json=json)
            return r.status_code, r.json()

    async def _delete(self, path: str, params: dict[str, Any]) -> int:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.delete(self.base + path, headers=self.headers, params=params)
            return r.status_code

    # Providers
    async def create_provider(self, data: dict[str, Any]) -> dict[str, Any]:
        code, body = await self._post("/model_providers", data)
        if code >= 300:
            raise RuntimeError(str(body))
        return body[0] if isinstance(body, list) and body else body

    async def list_providers(
        self, filters: dict[str, Any], page: int, page_size: int
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "select": "*",
            "offset": (page - 1) * page_size,
            "limit": page_size,
        }
        for k, v in filters.items():
            if v is None or v == "":
                continue
            params[k] = f"eq.{v}"
        code, items = await self._get("/model_providers", params)
        if code >= 300:
            raise RuntimeError(str(items))
        # total count via head request not implemented; return length
        return {"items": items, "total": len(items), "page": page, "page_size": page_size}

    async def delete_provider(self, provider_id: str) -> None:
        code = await self._delete("/model_providers", {"id": f"eq.{provider_id}"})
        if code >= 300:
            raise RuntimeError("delete failed")

    # Credentials
    async def upsert_credentials(
        self, provider_id: str, env: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        payload = {"provider_id": provider_id, "env": env, **data}
        code, body = await self._post("/model_credentials", payload)
        if code >= 300:
            raise RuntimeError(str(body))
        return body[0] if isinstance(body, list) and body else body

    async def list_credentials(self, provider_id: str) -> list[dict[str, Any]]:
        code, body = await self._get("/model_credentials", {"provider_id": f"eq.{provider_id}"})
        if code >= 300:
            raise RuntimeError(str(body))
        return body

    async def delete_credentials(self, provider_id: str, env: str) -> None:
        code = await self._delete(
            "/model_credentials", {"provider_id": f"eq.{provider_id}", "env": f"eq.{env}"}
        )
        if code >= 300:
            raise RuntimeError("delete failed")

    # Task Bindings
    async def create_binding(self, data: dict[str, Any]) -> dict[str, Any]:
        code, body = await self._post("/task_bindings", data)
        if code >= 300:
            raise RuntimeError(str(body))
        return body[0] if isinstance(body, list) and body else body

    async def list_bindings(self, task_name: str, env: str) -> list[dict[str, Any]]:
        code, body = await self._get(
            "/task_bindings", {"task_name": f"eq.{task_name}", "env": f"eq.{env}"}
        )
        if code >= 300:
            raise RuntimeError(str(body))
        return body

    # Metrics & Dashboard (basic counts)
    async def dashboard_stats(self) -> dict[str, Any]:
        code_p, providers = await self._get("/model_providers", {"select": "id,status"})
        code_b, bindings = await self._get("/task_bindings", {"select": "id"})
        if code_p >= 300:
            raise RuntimeError(str(providers))
        if code_b >= 300:
            raise RuntimeError(str(bindings))
        active = sum(1 for p in providers if p.get("status") == "active")
        return {"providers": len(providers), "active_providers": active, "tasks": len(bindings)}

    # Audit Logs
    async def create_audit(self, data: dict[str, Any]) -> dict[str, Any]:
        code, body = await self._post("/audit_logs", data)
        if code >= 300:
            raise RuntimeError(str(body))
        return body[0] if isinstance(body, list) and body else body

    async def list_audit(self, page: int, page_size: int) -> dict[str, Any]:
        code, logs = await self._get(
            "/audit_logs",
            {
                "select": "*",
                "order": "created_at.desc",
                "offset": (page - 1) * page_size,
                "limit": page_size,
            },
        )
        if code >= 300:
            raise RuntimeError(str(logs))
        return {"logs": logs, "total": len(logs), "page": page, "page_size": page_size}
