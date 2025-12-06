import os
import numpy as np
import asyncio
import httpx
from typing import List
import time
from prometheus_client import Counter, Histogram
from sqlalchemy.future import select
from server.database import AsyncSessionLocal
from server.models import Provider, ModelConfig

# Metrics
embed_errors = Counter('rag_embedding_errors_total', 'Embedding errors', ['provider'])
embed_latency = Histogram('rag_embedding_latency_seconds', 'Embedding latency', ['provider'])

class Embedder:
    def __init__(self, dim: int = 256, model_name: str | None = None):
        self.dim = dim
        self.model_name = model_name
        self.provider_config = None
        self.model_config = None
        # Lazy load config in async method or use sync check?
        # Constructor cannot be async. We will load config on first call or assume standard init.
        
        # We can't load DB in __init__ easily without sync loop.
        # We will try to resolve in embed_batch

    async def _ensure_config(self):
        if self.provider_config:
            return

        # Try to find model in DB by ID
        target_model = self.model_name or "BAAI/bge-m3"
        
        async with AsyncSessionLocal() as session:
            # Find Model Config
            res = await session.execute(select(ModelConfig).where(
                ModelConfig.model_id == target_model, 
                ModelConfig.is_active == True,
                ModelConfig.type == 'embedding'
            ))
            model_cfg = res.scalars().first()
            
            if model_cfg:
                self.model_config = model_cfg
                # Get Provider
                res_prov = await session.execute(select(Provider).where(Provider.id == model_cfg.provider_id))
                self.provider_config = res_prov.scalars().first()
            else:
                # Fallback: Look for any default embedding model
                if not self.model_name:
                    res = await session.execute(select(ModelConfig).where(
                        ModelConfig.is_default == True, 
                        ModelConfig.type == 'embedding'
                    ))
                    model_cfg = res.scalars().first()
                    if model_cfg:
                        self.model_config = model_cfg
                        res_prov = await session.execute(select(Provider).where(Provider.id == model_cfg.provider_id))
                        self.provider_config = res_prov.scalars().first()

    async def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([])
            
        await self._ensure_config()
        
        start = time.perf_counter()
        try:
            if self.provider_config:
                # Use DB Configured Provider
                provider_type = self.provider_config.name.lower()
                
                if "dashscope" in provider_type:
                    with embed_latency.labels(provider="dashscope").time():
                        return await self._embed_generic_api(texts)
                
                if "openai" in provider_type:
                    with embed_latency.labels(provider="openai").time():
                        return await self._embed_generic_api(texts)
                        
                # Add other providers here
            
            # Fallback to legacy/local behavior if DB config missing
            # ... (Legacy env var logic) ...
            return self._simple_embed_batch(texts)
            
        except Exception as e:
            embed_errors.labels(provider="auto").inc()
            return self._simple_embed_batch(texts)

    async def _embed_generic_api(self, texts: List[str]) -> np.ndarray:
        headers = {
            "Authorization": f"Bearer {self.provider_config.api_key}",
            "Content-Type": "application/json",
        }
        
        base_url = self.provider_config.base_url
        # Adjust URL for embedding endpoint
        if "dashscope" in base_url:
             url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/latest"
        elif "openai" in base_url:
             url = f"{base_url.rstrip('/')}/embeddings"
        else:
             url = f"{base_url.rstrip('/')}/embeddings" # Standard assumption

        payload = {
            "model": self.model_config.model_id,
            "input": texts
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                # Generic response parsing (OpenAI format)
                # DashScope format is slightly different ("output": {"embeddings": ...})
                if "data" in data:
                    embeddings = [item["embedding"] for item in data["data"]]
                elif "output" in data and "embeddings" in data["output"]:
                    embeddings = [item["embedding"] for item in data["output"]["embeddings"]]
                else:
                    raise ValueError("Unknown response format")
                return np.array(embeddings)
            else:
                raise ValueError(f"API Error {resp.status_code}")

    def _simple_embed_batch(self, texts: List[str]) -> np.ndarray:
        from core.embedding.simple_embedder import embed
        return np.stack([embed(t, self.dim) for t in texts])

    def embed(self, text: str) -> np.ndarray:
        try:
            loop = asyncio.get_event_loop()
        except:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.embed_batch([text]))[0]
