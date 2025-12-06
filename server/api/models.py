import os
import yaml
from typing import List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import time
import asyncio

from core.embedding.registry import get_embedder

router = APIRouter()

class ModelItem(BaseModel):
    id: str
    name: str
    provider: str
    type: str
    description: str | None = None
    status: str = "unknown"
    latency_ms: float = 0.0

def load_models_config() -> Dict[str, List[Dict]]:
    config_path = os.environ.get("MODELS_CONFIG_PATH", "data/config/models.yaml")
    if not os.path.exists(config_path):
        # Fallback defaults if file missing
        return {
            "embedding": [
                {"id": "BAAI/bge-m3", "name": "BGE M3 (Default)", "provider": "local/huggingface"}
            ]
        }
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

@router.get("/embedding")
async def list_embedding_models() -> List[ModelItem]:
    config = load_models_config()
    items = config.get("embedding", [])
    return [
        ModelItem(
            id=m["id"],
            name=m["name"],
            provider=m.get("provider", "unknown"),
            type="embedding",
            description=m.get("description")
        )
        for m in items
    ]

@router.post("/embedding/{model_id}/check")
async def check_embedding_model(model_id: str):
    try:
        embedder = get_embedder(model_name=model_id)
        t0 = time.perf_counter()
        # Dry run
        if asyncio.iscoroutinefunction(embedder.embed_batch):
            await embedder.embed_batch(["ping"])
        else:
            await asyncio.to_thread(embedder.embed_batch, ["ping"])
        dur = (time.perf_counter() - t0) * 1000
        return {"status": "available", "latency_ms": round(dur, 2)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
