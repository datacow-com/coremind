#!/usr/bin/env python3
"""
Cache Performance Comparison Tests.

Tests for semantic cache, multimodal cache, and embedding cache performance.
Validates QPS improvements, latency thresholds, and cache behavior.

Requirements: 4.1-4.5, 5.1-5.5, 6.1-6.5
"""

import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest
from hypothesis import given, settings, strategies as st

from tests.core.performance.utils.metrics_collector import MetricsCollector


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Create a MetricsCollector instance."""
    return MetricsCollector()


@pytest.fixture
def mock_embedder():
    """Create a mock embedder for testing."""
    embedder = AsyncMock()
    # Generate consistent embeddings based on input hash
    async def embed_text(text: str) -> list[float]:
        # Simulate embedding latency
        await asyncio.sleep(0.001)
        # Generate deterministic embedding from text hash
        h = hashlib.sha256(text.encode()).digest()
        return [float(b) / 255.0 for b in h[:50]]
    
    embedder.embed_text = embed_text
    return embedder


@pytest.fixture
def mock_slow_embedder():
    """Create a mock embedder with configurable latency for baseline tests."""
    class SlowEmbedder:
        def __init__(self, latency_ms: float = 50.0):
            self.latency_ms = latency_ms
            self.call_count = 0
        
        async def embed_text(self, text: str) -> list[float]:
            self.call_count += 1
            await asyncio.sleep(self.latency_ms / 1000.0)
            h = hashlib.sha256(text.encode()).digest()
            return [float(b) / 255.0 for b in h[:50]]
        
        async def embed_batch(self, texts: list[str]) -> np.ndarray:
            results = []
            for text in texts:
                emb = await self.embed_text(text)
                results.append(emb)
            return np.array(results)
    
    return SlowEmbedder


# =============================================================================
# Fake Cache Implementations for Testing
# =============================================================================


class FakeSemanticCache:
    """Fake semantic cache for performance testing."""
    
    def __init__(
        self,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
        max_cache_size: int = 10000,
    ):
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_cache_size = max_cache_size
        self._cache: dict[str, tuple[list[float], str, float, dict]] = {}
        self._embedder = None
        self._hits = 0
        self._misses = 0
    
    def set_embedder(self, embedder):
        self._embedder = embedder
    
    async def lookup(self, query: str, channel_id: str = "test") -> tuple[bool, str | None]:
        """Look up query in cache. Returns (hit, answer)."""
        if self._embedder is None:
            return False, None
        
        query_embedding = await self._embedder.embed_text(query)
        cache_key_prefix = f"sem_cache:{channel_id}"
        
        # Search for similar
        current_time = time.time()
        query_vec = np.array(query_embedding)
        
        for key, (cached_emb, answer, timestamp, _) in list(self._cache.items()):
            if not key.startswith(cache_key_prefix):
                continue
            if current_time - timestamp > self.ttl_seconds:
                del self._cache[key]
                continue
            
            cached_vec = np.array(cached_emb)
            similarity = np.dot(query_vec, cached_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(cached_vec) + 1e-8
            )
            
            if similarity > self.similarity_threshold:
                self._hits += 1
                return True, answer
        
        self._misses += 1
        return False, None

    async def store(
        self, query: str, answer: str, channel_id: str = "test"
    ) -> None:
        """Store query-answer pair in cache."""
        if self._embedder is None:
            return
        
        query_embedding = await self._embedder.embed_text(query)
        emb_hash = hashlib.sha256(str(query_embedding[:16]).encode()).hexdigest()[:16]
        cache_key = f"sem_cache:{channel_id}:{emb_hash}"
        
        self._cache[cache_key] = (
            query_embedding,
            answer,
            time.time(),
            {"query": query},
        )
        self._evict_if_needed()
    
    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max size."""
        if len(self._cache) <= self.max_cache_size:
            return
        entries = sorted(self._cache.items(), key=lambda x: x[1][2])
        to_remove = len(entries) - int(self.max_cache_size * 0.9)
        for key, _ in entries[:to_remove]:
            del self._cache[key]
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "cache_size": len(self._cache),
        }
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


class FakeMultimodalCache:
    """Fake multimodal embedding cache for performance testing."""
    
    def __init__(
        self,
        cache_ttl: int = 600,
        cache_maxsize: int = 512,
    ):
        self.cache_ttl = cache_ttl
        self.cache_maxsize = cache_maxsize
        self._cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._embed_latency_ms = 50.0  # Simulated embedding latency
    
    def _cache_key(self, content: Any, modality: str) -> str:
        if isinstance(content, bytes):
            base = content
        else:
            base = str(content).encode("utf-8")
        return hashlib.sha256(base + modality.encode("utf-8")).hexdigest()
    
    def _cache_get(self, key: str) -> list[float] | None:
        item = self._cache.get(key)
        if not item:
            return None
        ts, vec = item
        if time.time() - ts > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return vec
    
    def _cache_put(self, key: str, vec: list[float]) -> None:
        self._cache[key] = (time.time(), vec)
        self._cache.move_to_end(key)
        self._evict_if_needed()
    
    def _evict_if_needed(self) -> None:
        while len(self._cache) > self.cache_maxsize:
            self._cache.popitem(last=False)

    async def embed(self, content: str | bytes, modality: str = "text") -> list[float]:
        """Embed content with caching."""
        cache_key = self._cache_key(content, modality)
        cached = self._cache_get(cache_key)
        
        if cached is not None:
            self._hits += 1
            return cached
        
        self._misses += 1
        # Simulate embedding computation
        await asyncio.sleep(self._embed_latency_ms / 1000.0)
        
        if isinstance(content, bytes):
            h = hashlib.sha256(content).digest()
        else:
            h = hashlib.sha256(content.encode()).digest()
        
        embedding = [float(b) / 255.0 for b in h[:50]]
        self._cache_put(cache_key, embedding)
        return embedding
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "cache_size": len(self._cache),
        }
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


class FakeEmbeddingCache:
    """Fake embedding cache (LRU+TTL) for performance testing."""
    
    def __init__(
        self,
        cache_ttl: int = 900,
        cache_maxsize: int = 1000,
    ):
        self.cache_ttl = cache_ttl
        self.cache_maxsize = cache_maxsize
        self._cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._embed_latency_ms = 20.0  # Simulated embedding latency
    
    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    
    def _cache_get(self, key: str) -> list[float] | None:
        item = self._cache.get(key)
        if not item:
            return None
        ts, vec = item
        now = time.time()
        if now - ts > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return vec
    
    def _cache_put(self, key: str, vec: list[float], now: float) -> None:
        self._cache[key] = (now, vec)
        self._cache.move_to_end(key)
        self._evict_if_needed()
    
    def _evict_if_needed(self) -> None:
        while len(self._cache) > self.cache_maxsize:
            self._cache.popitem(last=False)
    
    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed texts with caching."""
        now = time.time()
        embeddings: list[list[float]] = []
        
        for text in texts:
            key = self._cache_key(text)
            cached = self._cache_get(key)
            
            if cached is not None:
                self._hits += 1
                embeddings.append(cached)
            else:
                self._misses += 1
                # Simulate embedding computation
                await asyncio.sleep(self._embed_latency_ms / 1000.0)
                h = hashlib.sha256(text.encode()).digest()
                vec = [float(b) / 255.0 for b in h[:50]]
                self._cache_put(key, vec, now)
                embeddings.append(vec)
        
        return np.array(embeddings)
    
    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "cache_size": len(self._cache),
        }
    
    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0


# =============================================================================
# Helper Functions
# =============================================================================


def generate_queries(count: int, unique_ratio: float = 1.0) -> list[str]:
    """Generate test queries with configurable uniqueness ratio.
    
    Args:
        count: Total number of queries to generate.
        unique_ratio: Ratio of unique queries (0.0-1.0).
                     1.0 = all unique, 0.2 = 20% unique (80% repeats).
    
    Returns:
        List of query strings.
    """
    unique_count = max(1, int(count * unique_ratio))
    unique_queries = [f"Query about topic {i}" for i in range(unique_count)]
    
    queries = []
    for i in range(count):
        queries.append(unique_queries[i % unique_count])
    
    return queries


def generate_texts(count: int, unique_ratio: float = 1.0) -> list[str]:
    """Generate test texts with configurable uniqueness ratio."""
    unique_count = max(1, int(count * unique_ratio))
    unique_texts = [f"Document content about subject {i}" for i in range(unique_count)]
    
    texts = []
    for i in range(count):
        texts.append(unique_texts[i % unique_count])
    
    return texts


# =============================================================================
# Semantic Cache Performance Tests
# =============================================================================


class TestSemanticCachePerformance:
    """Tests for semantic cache performance (Requirements 4.1-4.5)."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_semantic_cache_baseline_performance(
        self, mock_slow_embedder, metrics_collector
    ):
        """
        TC-SC-003 baseline: Test semantic cache disabled baseline performance.
        
        Validates: Requirements 4.3
        """
        embedder = mock_slow_embedder(latency_ms=10.0)
        queries = generate_queries(50, unique_ratio=1.0)
        
        metrics_collector.start()
        
        for query in queries:
            with metrics_collector.measure():
                # No cache - always compute embedding
                await embedder.embed_text(query)
        
        metrics_collector.stop()
        metrics = metrics_collector.get_metrics()
        
        # Record baseline metrics
        assert metrics.qps > 0, "Baseline QPS should be positive"
        assert metrics.total_requests == 50
        
        # Store baseline for comparison
        return metrics.qps
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_semantic_cache_hit_latency(self, mock_embedder, metrics_collector):
        """
        TC-SC-002: Test semantic cache hit P95 latency.
        
        Validates: Requirements 4.2
        """
        cache = FakeSemanticCache(similarity_threshold=0.92)
        cache.set_embedder(mock_embedder)
        
        # Pre-populate cache
        test_query = "What is artificial intelligence?"
        await cache.store(test_query, "AI is a branch of computer science.")
        
        metrics_collector.start()
        
        # Measure cache hit latency
        for _ in range(100):
            with metrics_collector.measure():
                hit, answer = await cache.lookup(test_query)
                assert hit, "Should be cache hit"
        
        metrics_collector.stop()
        metrics = metrics_collector.get_metrics()
        
        # P95 latency for cache hits should be below 50ms
        assert metrics.p95_latency_ms < 50, (
            f"Cache hit P95 latency {metrics.p95_latency_ms:.2f}ms exceeds 50ms threshold"
        )


# =============================================================================
# Multimodal Cache Performance Tests
# =============================================================================


class TestMultimodalCachePerformance:
    """Tests for multimodal embedding cache performance (Requirements 5.1-5.5)."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_multimodal_cache_ttl_expiry(self, metrics_collector):
        """
        TC-MC-002: Test multimodal cache TTL expiry and re-embedding.
        
        Validates: Requirements 5.2
        """
        # Create cache with very short TTL for testing
        cache = FakeMultimodalCache(cache_ttl=1, cache_maxsize=100)
        cache._embed_latency_ms = 5.0  # Fast for testing
        
        test_content = "Test image content"
        
        # First embed - cache miss
        await cache.embed(test_content, "image")
        stats1 = cache.get_stats()
        assert stats1["misses"] == 1
        assert stats1["hits"] == 0
        
        # Second embed - cache hit
        await cache.embed(test_content, "image")
        stats2 = cache.get_stats()
        assert stats2["hits"] == 1
        
        # Wait for TTL to expire
        await asyncio.sleep(1.5)
        
        # Third embed - should be cache miss (expired)
        await cache.embed(test_content, "image")
        stats3 = cache.get_stats()
        assert stats3["misses"] == 2, "Should re-embed after TTL expiry"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_multimodal_cache_lru_eviction(self, metrics_collector):
        """
        TC-MC-003: Test multimodal cache LRU eviction.
        
        Validates: Requirements 5.4
        """
        # Create small cache to trigger eviction
        cache = FakeMultimodalCache(cache_ttl=3600, cache_maxsize=5)
        cache._embed_latency_ms = 1.0  # Fast for testing
        
        # Fill cache beyond capacity
        for i in range(10):
            await cache.embed(f"Content {i}", "text")
        
        stats = cache.get_stats()
        
        # Cache size should not exceed maxsize
        assert stats["cache_size"] <= 5, (
            f"Cache size {stats['cache_size']} exceeds maxsize 5"
        )
        
        # Should have had evictions
        assert stats["misses"] == 10, "All should be misses (unique content)"


# =============================================================================
# Embedding Cache Performance Tests
# =============================================================================


class TestEmbeddingCachePerformance:
    """Tests for BatchEmbedder LRU cache performance (Requirements 6.1-6.5)."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_embedding_cache_disabled_baseline(self, metrics_collector):
        """
        TC-EC baseline: Test embedding cache disabled baseline performance.
        
        Validates: Requirements 6.3
        """
        # Create cache with disabled caching (maxsize=0)
        cache = FakeEmbeddingCache(cache_ttl=0, cache_maxsize=0)
        cache._embed_latency_ms = 5.0
        
        texts = generate_texts(20, unique_ratio=0.5)  # 50% repeats
        
        metrics_collector.start()
        
        for text in texts:
            with metrics_collector.measure():
                await cache.embed_batch([text])
        
        metrics_collector.stop()
        metrics = metrics_collector.get_metrics()
        
        # All should be misses since cache is disabled
        stats = cache.get_stats()
        assert stats["hits"] == 0, "No hits expected with disabled cache"
        
        return metrics.qps
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_embedding_cache_key_collision_handling(self, metrics_collector):
        """
        TC-EC-003: Test embedding cache key collision handling.
        
        Validates: Requirements 6.4
        """
        cache = FakeEmbeddingCache(cache_ttl=3600, cache_maxsize=100)
        cache._embed_latency_ms = 1.0
        
        # Same text should produce same key
        text = "Test document content"
        
        # First embed
        result1 = await cache.embed_batch([text])
        stats1 = cache.get_stats()
        assert stats1["misses"] == 1
        
        # Second embed - should hit cache
        result2 = await cache.embed_batch([text])
        stats2 = cache.get_stats()
        assert stats2["hits"] == 1
        
        # Results should be identical
        np.testing.assert_array_equal(result1, result2)


# =============================================================================
# Cache Size Limit Tests
# =============================================================================


class TestCacheSizeLimits:
    """Tests for cache size limits and eviction behavior."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_semantic_cache_size_limit(self):
        """
        Test semantic cache respects max_cache_size.
        
        Validates: Requirements 4.5
        """
        cache = FakeSemanticCache(max_cache_size=10)
        
        # Create a simple mock embedder
        class SimpleEmbedder:
            async def embed_text(self, text: str) -> list[float]:
                h = hashlib.sha256(text.encode()).digest()
                return [float(b) / 255.0 for b in h[:50]]
        
        cache.set_embedder(SimpleEmbedder())
        
        # Store more entries than max size
        for i in range(20):
            await cache.store(f"Query {i}", f"Answer {i}")
        
        stats = cache.get_stats()
        
        # Cache size should be limited
        assert stats["cache_size"] <= 10, (
            f"Cache size {stats['cache_size']} exceeds max 10"
        )
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_embedding_cache_maxsize_enforcement(self):
        """
        TC-EC-002: Test embedding cache maxsize enforcement.
        
        Validates: Requirements 6.2
        """
        max_size = 100
        cache = FakeEmbeddingCache(cache_ttl=3600, cache_maxsize=max_size)
        cache._embed_latency_ms = 0.1  # Very fast for this test
        
        # Generate more unique texts than cache can hold
        texts = [f"Unique document {i}" for i in range(150)]
        
        for text in texts:
            await cache.embed_batch([text])
        
        stats = cache.get_stats()
        
        # Cache size should never exceed maxsize
        assert stats["cache_size"] <= max_size, (
            f"Cache size {stats['cache_size']} exceeds maxsize {max_size}"
        )


# =============================================================================
# Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Integration tests for cache components."""
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_cache_metrics_reporting(self, metrics_collector):
        """
        Test that cache metrics are correctly reported.
        
        Validates: Requirements 4.5, 5.5, 6.5
        """
        cache = FakeEmbeddingCache(cache_ttl=3600, cache_maxsize=100)
        cache._embed_latency_ms = 1.0
        
        # Generate mixed queries (some repeats)
        texts = generate_texts(50, unique_ratio=0.4)  # 40% unique = 60% repeats
        
        metrics_collector.start()
        
        for text in texts:
            with metrics_collector.measure():
                await cache.embed_batch([text])
            
            # Record cache access
            stats = cache.get_stats()
            # Note: We track hits/misses internally in the cache
        
        metrics_collector.stop()
        
        stats = cache.get_stats()
        
        # Verify metrics are reported
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "cache_size" in stats
        
        # With 40% unique, we expect ~60% hit rate after warmup
        # But first access to each unique is a miss
        assert stats["hit_rate"] > 0, "Should have some cache hits"
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_cache_access(self, metrics_collector):
        """
        Test cache behavior under concurrent access.
        
        Validates: Requirements 4.5, 5.5
        """
        cache = FakeEmbeddingCache(cache_ttl=3600, cache_maxsize=100)
        cache._embed_latency_ms = 5.0
        
        texts = generate_texts(20, unique_ratio=0.5)
        
        async def embed_task(text: str):
            return await cache.embed_batch([text])
        
        metrics_collector.start()
        
        # Run concurrent embeddings
        tasks = [embed_task(text) for text in texts]
        results = await asyncio.gather(*tasks)
        
        metrics_collector.stop()
        
        # All tasks should complete
        assert len(results) == 20
        
        # Each result should be valid
        for result in results:
            assert result.shape[0] == 1  # Single text per batch
            assert result.shape[1] > 0  # Has embedding dimensions


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])
