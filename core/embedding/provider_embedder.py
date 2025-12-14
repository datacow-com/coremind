import os
import numpy as np
import asyncio
import httpx
from typing import List
import time
import hashlib
from collections import OrderedDict
from prometheus_client import Counter, Histogram
from sqlalchemy.future import select
from server.database import AsyncSessionLocal
from server.models import Provider, ModelConfig

# Metrics
embed_errors = Counter('rag_embedding_errors_total', 'Embedding errors', ['provider'])
embed_latency = Histogram('rag_embedding_latency_seconds', 'Embedding latency', ['provider'])
embed_cache_hits = Counter('rag_embedding_cache_hits_total', 'Embedding cache hits', ['provider'])
embed_cache_misses = Counter('rag_embedding_cache_misses_total', 'Embedding cache misses', ['provider'])

class Embedder:
    def __init__(self, dim: int = 256, model_name: str | None = None):
        self.dim = dim
        self.model_name = model_name
        self.provider_config = None
        self.model_config = None
        # Cache settings (LRU + TTL)
        self.cache_ttl = int(os.environ.get("EMBED_CACHE_TTL", "900"))
        self.cache_maxsize = int(os.environ.get("EMBED_CACHE_MAXSIZE", "1000"))
        self._embed_cache: "OrderedDict[str, tuple[float, list[float]]]" = OrderedDict()
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

    def _init_cache(self):
        """Ensure cache exists; no-op placeholder for future pluggable cache."""
        if self._embed_cache is None:
            self._embed_cache = OrderedDict()

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str, now: float) -> list[float] | None:
        item = self._embed_cache.get(key)
        if not item:
            return None
        ts, vec = item
        if now - ts > self.cache_ttl:
            self._embed_cache.pop(key, None)
            return None
        # Refresh LRU order
        self._embed_cache.move_to_end(key)
        return vec

    def _cache_put(self, key: str, vec: list[float], now: float):
        self._embed_cache[key] = (now, vec)
        self._embed_cache.move_to_end(key)
        self._evict_if_needed()

    def _evict_if_needed(self):
        while len(self._embed_cache) > self.cache_maxsize:
            self._embed_cache.popitem(last=False)

    async def _compute_embeddings_no_cache(self, texts: List[str]) -> np.ndarray:
        """Original embedding computation without cache."""
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
            return self._simple_embed_batch(texts)

        except Exception:
            embed_errors.labels(provider="auto").inc()
            return self._simple_embed_batch(texts)

    async def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Embedding with LRU+TTL cache to reduce provider calls.
        """
        if not texts:
            return np.array([])

        self._init_cache()
        now = time.perf_counter()

        embeddings: list[list[float] | None] = [None] * len(texts)
        missing_texts: list[str] = []
        missing_indices: list[int] = []

        for idx, t in enumerate(texts):
            key = self._cache_key(t)
            cached = self._cache_get(key, now)
            if cached is not None:
                embed_cache_hits.labels(provider="text").inc()
                embeddings[idx] = cached
            else:
                embed_cache_misses.labels(provider="text").inc()
                missing_texts.append(t)
                missing_indices.append(idx)

        if missing_texts:
            computed = await self._compute_embeddings_no_cache(missing_texts)
            for i, vec in zip(missing_indices, computed.tolist(), strict=False):
                embeddings[i] = vec
                self._cache_put(self._cache_key(texts[i]), vec, now)

        # Backfill any failed entries with zero vectors to maintain shape
        filled = [
            e if e is not None else [0.0] * self.dim
            for e in embeddings
        ]
        return np.array(filled)

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
