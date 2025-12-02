from typing import Any

from .supabase_repo import SupabaseRepo


class SupabaseModelGatewayService:
    def __init__(self):
        self.repo = SupabaseRepo()

    async def create_model(
        self, model_data: dict[str, Any], user_id: str, user_name: str
    ) -> dict[str, Any]:
        created = await self.repo.create_provider(model_data)
        await self.repo.create_audit(
            {
                "actor_id": user_id,
                "actor_name": user_name,
                "action": "create_model",
                "resource_type": "model_provider",
                "resource_id": created.get("id"),
                "diff": model_data,
            }
        )
        return created

    async def list_models(
        self, filters: dict[str, Any], page: int, page_size: int
    ) -> dict[str, Any]:
        return await self.repo.list_providers(filters, page, page_size)

    async def update_model(
        self, model_id: str, model_data: dict[str, Any], user_id: str, user_name: str
    ) -> dict[str, Any] | None:
        # Supabase REST 不支持按 id patch 直接返回，这里使用 upsert 语义（示例简化：删除再创建或直接patch需要 RLS 规则）
        # 为简化示例，前端目前不提供编辑；此处留空或可实现 _patch。
        return None

    async def delete_model(self, model_id: str, user_id: str, user_name: str) -> bool:
        await self.repo.delete_provider(model_id)
        await self.repo.create_audit(
            {
                "actor_id": user_id,
                "actor_name": user_name,
                "action": "delete_model",
                "resource_type": "model_provider",
                "resource_id": model_id,
            }
        )
        return True

    async def create_task_binding(
        self, binding_data: dict[str, Any], user_id: str, user_name: str
    ) -> dict[str, Any]:
        created = await self.repo.create_binding(binding_data)
        await self.repo.create_audit(
            {
                "actor_id": user_id,
                "actor_name": user_name,
                "action": "create_task_binding",
                "resource_type": "task_binding",
                "resource_id": created.get("id"),
                "diff": binding_data,
            }
        )
        return created

    async def get_task_bindings(self, task_name: str, environment: str) -> list[dict[str, Any]]:
        return await self.repo.list_bindings(task_name, environment)

    async def get_dashboard_stats(self) -> dict[str, Any]:
        return await self.repo.dashboard_stats()

    async def get_audit_logs(self, page: int, page_size: int) -> dict[str, Any]:
        return await self.repo.list_audit(page, page_size)

    # Credentials
    async def upsert_credentials(
        self, provider_id: str, env: str, data: dict[str, Any], user_id: str, user_name: str
    ) -> dict[str, Any]:
        cred = await self.repo.upsert_credentials(provider_id, env, data)
        await self.repo.create_audit(
            {
                "actor_id": user_id,
                "actor_name": user_name,
                "action": "upsert_credentials",
                "resource_type": "model_credentials",
                "resource_id": cred.get("id"),
                "diff": {"env": env, **data},
            }
        )
        return cred

    async def list_credentials(self, provider_id: str) -> list[dict[str, Any]]:
        return await self.repo.list_credentials(provider_id)

    async def delete_credentials(
        self, provider_id: str, env: str, user_id: str, user_name: str
    ) -> bool:
        await self.repo.delete_credentials(provider_id, env)
        await self.repo.create_audit(
            {
                "actor_id": user_id,
                "actor_name": user_name,
                "action": "delete_credentials",
                "resource_type": "model_credentials",
                "resource_id": provider_id,
                "diff": {"env": env},
            }
        )
        return True
