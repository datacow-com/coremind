import asyncio
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.future import select

from core.embedding.registry import get_embedder
from core.llm.gateway import LLMGateway
from server.database import get_db
from server.models import ModelConfig, Provider

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

if prometheus_client:
    _H_MODEL_CHECK = prometheus_client.Histogram(
        "api_model_check_duration_ms",
        "Model check latency (ms)",
        ["type", "model"],
        buckets=(10, 20, 50, 100, 200, 500, 1000, 2000, 5000),
    )
    _C_MODEL_CHECK_ERR = prometheus_client.Counter(
        "api_model_check_errors", "Model check errors", ["type", "model"]
    )
else:  # pragma: no cover
    _H_MODEL_CHECK = _C_MODEL_CHECK_ERR = None


def _observe(model_type: str, model_id: str, dur_ms: float | None, error: bool = False):
    if _H_MODEL_CHECK and dur_ms is not None:
        try:
            _H_MODEL_CHECK.labels(model_type, model_id).observe(dur_ms)
        except Exception:
            pass
    if error and _C_MODEL_CHECK_ERR:
        try:
            _C_MODEL_CHECK_ERR.labels(model_type, model_id).inc()
        except Exception:
            pass


router = APIRouter()


class ModelItem(BaseModel):
    id: str
    name: str
    provider: str
    type: str
    description: str | None = None
    status: str = "unknown"
    latency_ms: float = 0.0


async def _list_db_models(model_type: str, db) -> list[ModelItem]:
    q = (
        select(ModelConfig, Provider)
        .join(Provider, Provider.id == ModelConfig.provider_id)
        .where(ModelConfig.is_active == True, ModelConfig.type.ilike(model_type))
    )
    res = await db.execute(q)
    out: list[ModelItem] = []
    for mdl, prov in res.all():
        out.append(
            ModelItem(
                id=mdl.model_id,
                name=mdl.name,
                provider=prov.name,
                type=model_type,
                description=prov.description,
            )
        )
    return out


@router.get("/embedding")
async def list_embedding_models(db=Depends(get_db)) -> list[ModelItem]:
    return await _list_db_models("embedding", db)


@router.get("/ocr")
async def list_ocr_models(db=Depends(get_db)) -> list[ModelItem]:
    return await _list_db_models("ocr", db)


@router.get("/llm")
async def list_llm_models(db=Depends(get_db)) -> list[ModelItem]:
    return await _list_db_models("llm", db)


@router.get("/rerank")
async def list_rerank_models(db=Depends(get_db)) -> list[ModelItem]:
    return await _list_db_models("rerank", db)


@router.post("/embedding/{model_id}/check")
async def check_embedding_model(model_id: str, db=Depends(get_db)):
    # 查 DB provider -> model
    res = await db.execute(
        select(ModelConfig, Provider)
        .join(Provider, Provider.id == ModelConfig.provider_id)
        .where(
            ModelConfig.model_id == model_id,
            ModelConfig.is_active == True,
            Provider.is_active == True,
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="model not found")
    try:
        embedder = get_embedder(model_name=model_id)
        t0 = time.perf_counter()
        if asyncio.iscoroutinefunction(embedder.embed_batch):
            await embedder.embed_batch(["ping"])
        else:
            await asyncio.to_thread(embedder.embed_batch, ["ping"])
        dur = (time.perf_counter() - t0) * 1000
        _observe("embedding", model_id, dur, error=False)
        return {"status": "available", "latency_ms": round(dur, 2)}
    except Exception as e:
        _observe("embedding", model_id, None, error=True)
        return {"status": "error", "error": str(e)}


def _env_check(model: dict[str, Any]) -> dict[str, Any]:
    # 简单环境校验：如果配置中有 provider，则查 REQUIRED_ENV；若模型自带 api_key 也视为可用
    provider = (model.get("provider") or "").lower()
    envs = REQUIRED_ENV.get(provider, [])
    missing = [e for e in envs if not os.environ.get(e)]
    if model.get("api_key"):
        missing = []
    return {
        "status": "available" if not missing else "error",
        "missing_env": missing,
    }


@router.post("/ocr/{model_id}/check")
async def check_ocr_model(model_id: str, db=Depends(get_db)):
    res = await db.execute(
        select(ModelConfig, Provider)
        .join(Provider, Provider.id == ModelConfig.provider_id)
        .where(
            ModelConfig.model_id == model_id,
            ModelConfig.type.ilike("ocr"),
            ModelConfig.is_active == True,
            Provider.is_active == True,
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="model not found")
    mdl, prov = row
    base_url = prov.base_url or ""
    api_key = prov.api_key or os.environ.get("OCR_API_KEY")
    if not base_url:
        return {"status": "error", "error": "missing base_url"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        t0 = time.perf_counter()
        timeout = float(os.environ.get("MODEL_CHECK_TIMEOUT", "5"))
        with httpx.Client(timeout=timeout) as client:
            r = client.get(base_url, headers=headers)
            r.raise_for_status()
        dur = (time.perf_counter() - t0) * 1000
        _observe("ocr", model_id, dur, error=False)
        return {"status": "available", "latency_ms": round(dur, 2)}
    except Exception as e:
        _observe("ocr", model_id, None, error=True)
        return {"status": "error", "error": str(e)}


@router.post("/llm/{model_id}/check")
async def check_llm_model(model_id: str, db=Depends(get_db)):
    res = await db.execute(
        select(ModelConfig, Provider)
        .join(Provider, Provider.id == ModelConfig.provider_id)
        .where(
            ModelConfig.model_id == model_id,
            ModelConfig.type.ilike("llm"),
            ModelConfig.is_active == True,
            Provider.is_active == True,
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="model not found")
    mdl, prov = row
    try:
        gateway = LLMGateway(provider=prov.name, model=mdl.model_id)
        t0 = time.perf_counter()
        out = await gateway.chat("ping")
        dur = (time.perf_counter() - t0) * 1000
        if not out:
            return {"status": "error", "error": "empty response"}
        _observe("llm", model_id, dur, error=False)
        return {"status": "available", "latency_ms": round(dur, 2)}
    except Exception as e:
        _observe("llm", model_id, None, error=True)
        return {"status": "error", "error": str(e)}


@router.post("/rerank/{model_id}/check")
async def check_rerank_model(model_id: str, db=Depends(get_db)):
    res = await db.execute(
        select(ModelConfig, Provider)
        .join(Provider, Provider.id == ModelConfig.provider_id)
        .where(
            ModelConfig.model_id == model_id,
            ModelConfig.type.ilike("rerank"),
            ModelConfig.is_active == True,
            Provider.is_active == True,
        )
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="model not found")
    mdl, prov = row
    base_url = prov.base_url or ""
    api_key = prov.api_key or os.environ.get("RERANK_API_KEY")
    if not base_url:
        return {"status": "error", "error": "missing base_url"}
    headers = (
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        if api_key
        else {"Content-Type": "application/json"}
    )
    try:
        timeout = float(os.environ.get("MODEL_CHECK_TIMEOUT", "5"))
        payload = {"model": mdl.model_id, "input": [{"text": "a"}, {"text": "b"}]}
        t0 = time.perf_counter()
        with httpx.Client(timeout=timeout) as client:
            r = client.post(base_url.rstrip("/") + "/rerank", json=payload, headers=headers)
            r.raise_for_status()
        dur = (time.perf_counter() - t0) * 1000
        _observe("rerank", model_id, dur, error=False)
        return {"status": "available", "latency_ms": round(dur, 2)}
    except Exception as e:
        _observe("rerank", model_id, None, error=True)
        return {"status": "error", "error": str(e)}
