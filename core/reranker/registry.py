import os
from typing import Protocol

from sqlalchemy.future import select

from core.reranker.cohere_reranker import CohereReranker as _CohereReranker
from core.reranker.cross_encoder import Reranker as _CrossEncoderReranker
from core.reranker.http_reranker import HttpReranker as _HttpReranker
from server.database import AsyncSessionLocal
from server.models import ModelConfig, Provider


class RerankerProtocol(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


def _cohere_available() -> bool:
    try:
        return bool(os.environ.get("COHERE_API_KEY"))
    except Exception:
        return False


async def _load_model(
    provider: str | None, model: str | None
) -> tuple[Provider | None, ModelConfig | None]:
    async with AsyncSessionLocal() as session:
        # 模型直查
        if model:
            res = await session.execute(
                select(ModelConfig).where(
                    ModelConfig.model_id == model,
                    ModelConfig.is_active == True,
                    ModelConfig.type.ilike("rerank"),
                )
            )
            mdl = res.scalars().first()
            if mdl:
                resp = await session.execute(
                    select(Provider).where(
                        Provider.id == mdl.provider_id,
                        Provider.is_active == True,
                        Provider.category.ilike("reranker"),
                    )
                )
                prov = resp.scalars().first()
                if prov:
                    return prov, mdl

        # provider 优先
        if provider:
            res = await session.execute(
                select(Provider).where(
                    Provider.name.ilike(provider),
                    Provider.is_active == True,
                    Provider.category.ilike("reranker"),
                )
            )
            prov = res.scalars().first()
            if not prov:
                return None, None
            resm = await session.execute(
                select(ModelConfig).where(
                    ModelConfig.provider_id == prov.id,
                    ModelConfig.is_active == True,
                    ModelConfig.is_default == True,
                    ModelConfig.type.ilike("rerank"),
                )
            )
            mdl = resm.scalars().first()
            return prov, mdl
    return None, None


async def get_reranker(
    provider: str | None = None,
    model_id: str | None = None,
    fallback_models: list[str] | None = None,
) -> RerankerProtocol:
    """
    Reranker 选择策略：
    1) 如果 DB 中存在 rerank 模型：优先使用 HTTP reranker（base_url/model 从 DB）
       - 如请求未提供模型，则取指定 provider 的默认模型
    2) 若 DB 无匹配模型，则使用 cohere / cross_encoder / simple 回退
    """
    # 先尝试 DB
    prov, mdl = await _load_model(provider, model_id)
    if not prov and fallback_models:
        for mid in fallback_models:
            prov, mdl = await _load_model(provider, mid)
            if prov and mdl:
                break
    if prov and mdl and prov.base_url:
        timeout = float(os.environ.get("RERANK_HTTP_TIMEOUT", "8"))
        return _HttpReranker(
            base_url=prov.base_url, api_key=prov.api_key, model=mdl.model_id, timeout=timeout
        )

    # 环境回退
    name = (provider or os.environ.get("RERANKER_PROVIDER") or "auto").lower()
    if name == "cohere" and _cohere_available():
        return _CohereReranker()
    if name == "cross_encoder":
        return _CrossEncoderReranker()
    if name == "simple":
        return _CrossEncoderReranker(model_name=None)  # fallback overlap
    if _cohere_available():
        return _CohereReranker()
    return _CrossEncoderReranker()
