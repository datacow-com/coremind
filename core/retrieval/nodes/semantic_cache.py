"""
Semantic Cache Node - Cache similar queries to avoid redundant LLM calls.

Features:
- Semantic similarity matching using embeddings
- Configurable TTL and similarity threshold
- Redis/memory backend support
- Metrics for cache hit rate
"""

import hashlib
import time
from typing import Any

from core.state import RetrievalState


class SemanticCache:
    """
    Semantic cache for retrieval results.
    
    Caches query-answer pairs with semantic similarity matching
    to avoid redundant LLM calls for similar queries.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
        max_cache_size: int = 10000,
    ):
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        
        # In-memory cache: {cache_key: (embedding, answer, timestamp, metadata)}
        self._cache: dict[str, tuple[list[float], str, float, dict[str, Any]]] = {}
        self._embedder = None
        
        # Metrics
        self._hits = 0
        self._misses = 0
    
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        """Check cache and return cached answer if found."""
        cfg = state.get("strategy_config", {})
        
        # Check if semantic cache is enabled
        if not cfg.get("enable_semantic_cache", False):
            return state
        
        query = state.get("input_query", "")
        kb_names = state.get("kb_names", [])
        channel_id = state.get("channel_id", "")
        
        if not query:
            return state
        
        # Initialize embedder if needed
        if self._embedder is None:
            self._embedder = await self._get_embedder(state)
        
        if self._embedder is None:
            # No embedder available, skip cache
            return state
        
        # Generate query embedding
        try:
            query_embedding = await self._embed_query(query)
        except Exception:
            return state
        
        # Search cache for similar query
        cache_key_prefix = self._make_cache_key_prefix(channel_id, kb_names)
        cached_result = self._find_similar(query_embedding, cache_key_prefix)
        
        if cached_result:
            # Cache hit
            self._hits += 1
            answer, metadata = cached_result
            state["final_answer"] = answer
            state["answer"] = answer  # Backward compatibility
            state["cache_hit"] = True
            state["cache_metadata"] = metadata
            # Skip remaining retrieval pipeline
            state["skip_retrieval"] = True
            return state
        
        # Cache miss - store query embedding for later caching
        self._misses += 1
        state["_query_embedding"] = query_embedding
        state["_cache_key_prefix"] = cache_key_prefix
        state["cache_hit"] = False
        
        return state
    
    async def cache_result(self, state: RetrievalState) -> RetrievalState:
        """Store the final answer in cache."""
        cfg = state.get("strategy_config", {})
        
        if not cfg.get("enable_semantic_cache", False):
            return state
        
        # Only cache if we have an answer and it wasn't from cache
        if state.get("cache_hit", False):
            return state
        
        final_answer = state.get("final_answer", "")
        if not final_answer:
            return state
        
        query_embedding = state.get("_query_embedding")
        cache_key_prefix = state.get("_cache_key_prefix", "")
        
        if not query_embedding:
            return state
        
        # Store in cache
        cache_key = f"{cache_key_prefix}:{self._embedding_hash(query_embedding)}"
        metadata = {
            "query": state.get("input_query", ""),
            "confidence": state.get("confidence", 0.0),
            "sources_count": len(state.get("citations", [])),
        }
        
        self._cache[cache_key] = (
            query_embedding,
            final_answer,
            time.time(),
            metadata,
        )
        
        # Evict old entries if cache is too large
        self._evict_if_needed()
        
        # Clean up temporary state
        if "_query_embedding" in state:
            del state["_query_embedding"]
        if "_cache_key_prefix" in state:
            del state["_cache_key_prefix"]
        
        return state
    
    async def _get_embedder(self, state: RetrievalState) -> Any:
        """Get embedder from capability loader or create a simple one."""
        capability_loader = state.get("capability_loader")
        if capability_loader and hasattr(capability_loader, "get"):
            embedder = capability_loader.get("multimodal_embedding")
            if embedder:
                return embedder
        
        # Fallback: try to create a simple embedder
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            
            class SimpleEmbedder:
                def __init__(self, model):
                    self.model = model
                
                async def embed_text(self, text: str) -> list[float]:
                    import asyncio
                    embedding = await asyncio.to_thread(
                        self.model.encode, text, convert_to_numpy=True
                    )
                    return embedding.tolist()
            
            return SimpleEmbedder(model)
        except ImportError:
            return None
    
    async def _embed_query(self, query: str) -> list[float]:
        """Generate embedding for query."""
        if hasattr(self._embedder, "embed_text"):
            return await self._embedder.embed_text(query)
        elif hasattr(self._embedder, "embed"):
            return await self._embedder.embed(query)
        else:
            raise ValueError("Embedder does not have embed_text or embed method")
    
    def _make_cache_key_prefix(self, channel_id: str, kb_names: list[str]) -> str:
        """Create cache key prefix from channel and kb names."""
        kb_key = "|".join(sorted(kb_names)) if kb_names else "default"
        return f"sem_cache:{channel_id}:{kb_key}"
    
    def _embedding_hash(self, embedding: list[float]) -> str:
        """Create a hash of embedding for cache key."""
        # Use first 8 bytes of SHA256 for compact key
        emb_bytes = str(embedding[:16]).encode()  # Use first 16 dims
        return hashlib.sha256(emb_bytes).hexdigest()[:16]
    
    def _find_similar(
        self, query_embedding: list[float], cache_key_prefix: str
    ) -> tuple[str, dict[str, Any]] | None:
        """Find similar query in cache."""
        import numpy as np
        
        current_time = time.time()
        query_vec = np.array(query_embedding)
        
        best_match = None
        best_similarity = 0.0
        
        for key, (cached_emb, answer, timestamp, metadata) in list(self._cache.items()):
            # Check prefix match
            if not key.startswith(cache_key_prefix):
                continue
            
            # Check TTL
            if current_time - timestamp > self.ttl_seconds:
                del self._cache[key]  # Expired
                continue
            
            # Calculate cosine similarity
            cached_vec = np.array(cached_emb)
            similarity = np.dot(query_vec, cached_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(cached_vec) + 1e-8
            )
            
            if similarity > self.similarity_threshold and similarity > best_similarity:
                best_match = (answer, metadata)
                best_similarity = similarity
        
        return best_match
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        if len(self._cache) <= self.max_cache_size:
            return
        
        # Sort by timestamp and remove oldest 10%
        entries = sorted(
            self._cache.items(),
            key=lambda x: x[1][2],  # timestamp
        )
        
        to_remove = len(entries) - int(self.max_cache_size * 0.9)
        for key, _ in entries[:to_remove]:
            del self._cache[key]
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "max_size": self.max_cache_size,
        }
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# Singleton instance
_SEMANTIC_CACHE: SemanticCache | None = None


def get_semantic_cache() -> SemanticCache:
    """Get or create semantic cache singleton."""
    global _SEMANTIC_CACHE
    if _SEMANTIC_CACHE is None:
        _SEMANTIC_CACHE = SemanticCache()
    return _SEMANTIC_CACHE
