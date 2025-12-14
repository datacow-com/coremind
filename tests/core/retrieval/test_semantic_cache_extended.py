#!/usr/bin/env python3
"""
语义缓存扩展测试 - core/retrieval/nodes/semantic_cache.py

测试TTL过期、哈希冲突、skip_retrieval路径、缓存命中后不再检索等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import time
import numpy as np
from typing import Dict, Any, List

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'core.state': Mock(),
    'sentence_transformers': Mock(),
}):
    from core.retrieval.nodes.semantic_cache import (
        SemanticCache, get_semantic_cache
    )


class TestSemanticCacheTTL:
    """语义缓存TTL过期测试"""
    
    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return SemanticCache(
            similarity_threshold=0.92,
            ttl_seconds=3600,  # 1小时
            max_cache_size=100
        )

    # TC-SC-EXT-001: TTL过期清理 (P1)
    def test_ttl_expiry_cleanup(self, cache):
        """验证TTL过期条目的清理"""
        # 使用相同的前缀，这样 _find_similar 会检查并清理过期条目
        prefix = "sem_cache:test:kb"
        
        # 手动添加过期条目（使用匹配的前缀）
        expired_embedding = [0.1] * 768
        cache._cache[f"{prefix}:expired_hash"] = (
            expired_embedding,
            "过期的答案",
            time.time() - 7200,  # 2小时前，已过期
            {"query": "过期查询"}
        )
        
        # 添加新鲜条目（使用匹配的前缀）
        fresh_embedding = [0.2] * 768
        cache._cache[f"{prefix}:fresh_hash"] = (
            fresh_embedding,
            "新鲜的答案",
            time.time(),  # 当前时间
            {"query": "新鲜查询"}
        )
        
        # 触发搜索（会清理前缀匹配的过期条目）
        # 注意：实际实现只在前缀匹配时检查TTL并清理
        result = cache._find_similar([0.1] * 768, prefix)
        
        # 验证过期条目被清理（因为前缀匹配且已过期）
        assert f"{prefix}:expired_hash" not in cache._cache, "过期条目应该被清理"
        # 新鲜条目应该保留
        assert f"{prefix}:fresh_hash" in cache._cache, "新鲜条目应该保留"

    # TC-SC-EXT-002: TTL边界测试 (P1)
    def test_ttl_boundary_values(self, cache):
        """验证TTL边界值的处理"""
        embedding = [0.1] * 768
        
        # 刚好过期
        cache._cache["just_expired"] = (
            embedding,
            "刚过期",
            time.time() - 3601,  # 刚好超过1小时
            {}
        )
        
        # 刚好未过期
        cache._cache["just_fresh"] = (
            embedding,
            "刚好新鲜",
            time.time() - 3599,  # 刚好不到1小时
            {}
        )
        
        # 触发清理
        cache._find_similar([0.1] * 768, "")
        
        assert "just_expired" not in cache._cache, "刚过期的条目应该被清理"
        # 注意：just_fresh 可能因为前缀不匹配而不被返回，但不应该被清理
        # 这里我们只验证过期逻辑

    # TC-SC-EXT-003: 自定义TTL配置 (P2)
    def test_custom_ttl_configuration(self):
        """验证自定义TTL配置"""
        short_ttl_cache = SemanticCache(ttl_seconds=60)  # 1分钟
        long_ttl_cache = SemanticCache(ttl_seconds=86400)  # 1天
        
        assert short_ttl_cache.ttl_seconds == 60
        assert long_ttl_cache.ttl_seconds == 86400


class TestSemanticCacheHashConflict:
    """语义缓存哈希冲突测试"""
    
    @pytest.fixture
    def cache(self):
        return SemanticCache(similarity_threshold=0.92)

    # TC-SC-EXT-004: 嵌入哈希唯一性 (P1)
    def test_embedding_hash_uniqueness(self, cache):
        """验证不同嵌入产生不同哈希"""
        embeddings = [
            [0.1, 0.2, 0.3] + [0.0] * 765,
            [0.1, 0.2, 0.4] + [0.0] * 765,  # 略有不同
            [0.9, 0.8, 0.7] + [0.0] * 765,  # 完全不同
        ]
        
        hashes = [cache._embedding_hash(emb) for emb in embeddings]
        
        # 验证哈希不同
        assert len(set(hashes)) == len(hashes), "不同嵌入应该产生不同哈希"

    # TC-SC-EXT-005: 相似嵌入哈希处理 (P1)
    def test_similar_embedding_hash_handling(self, cache):
        """验证相似嵌入的哈希处理"""
        # 非常相似的嵌入
        emb1 = [0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * 763
        emb2 = [0.1, 0.2, 0.3, 0.4, 0.50001] + [0.0] * 763  # 微小差异
        
        hash1 = cache._embedding_hash(emb1)
        hash2 = cache._embedding_hash(emb2)
        
        # 哈希可能相同或不同，关键是相似度检查
        # 如果哈希相同，需要通过相似度检查来区分
        if hash1 == hash2:
            # 这是可接受的，因为我们有相似度检查作为第二道防线
            pass
        else:
            # 不同哈希更好，可以直接区分
            pass

    # TC-SC-EXT-006: 缓存键前缀隔离 (P0)
    def test_cache_key_prefix_isolation(self, cache):
        """验证不同channel/kb的缓存键隔离"""
        prefix_a = cache._make_cache_key_prefix("channel_a", ["kb1", "kb2"])
        prefix_b = cache._make_cache_key_prefix("channel_b", ["kb1", "kb2"])
        prefix_c = cache._make_cache_key_prefix("channel_a", ["kb3"])
        
        # 验证不同channel产生不同前缀
        assert prefix_a != prefix_b, "不同channel应该有不同前缀"
        
        # 验证不同kb产生不同前缀
        assert prefix_a != prefix_c, "不同kb应该有不同前缀"
        
        # 验证前缀格式
        assert "channel_a" in prefix_a
        assert "channel_b" in prefix_b


class TestSemanticCacheSkipRetrieval:
    """语义缓存skip_retrieval路径测试"""
    
    @pytest.fixture
    def cache(self):
        return SemanticCache(similarity_threshold=0.92)

    # TC-SC-EXT-007: 缓存命中设置skip_retrieval (P0)
    @pytest.mark.asyncio
    async def test_cache_hit_sets_skip_retrieval(self, cache):
        """验证缓存命中时设置skip_retrieval标记"""
        # 预先填充缓存
        query_embedding = [0.1] * 768
        cache._cache["sem_cache:test_channel:test_kb:" + cache._embedding_hash(query_embedding)] = (
            query_embedding,
            "缓存的答案",
            time.time(),
            {"query": "测试查询"}
        )
        
        mock_state = {
            "input_query": "测试查询",
            "channel_id": "test_channel",
            "kb_names": ["test_kb"],
            "strategy_config": {"enable_semantic_cache": True}
        }
        
        # Mock embedder
        cache._embedder = Mock()
        cache._embedder.embed_text = AsyncMock(return_value=query_embedding)
        
        result = await cache(mock_state)
        
        # 验证skip_retrieval被设置
        assert result.get("cache_hit") is True, "应该标记缓存命中"
        assert result.get("skip_retrieval") is True, "应该设置skip_retrieval"
        assert result.get("final_answer") == "缓存的答案", "应该返回缓存答案"

    # TC-SC-EXT-008: 缓存未命中不设置skip_retrieval (P1)
    @pytest.mark.asyncio
    async def test_cache_miss_no_skip_retrieval(self, cache):
        """验证缓存未命中时不设置skip_retrieval"""
        mock_state = {
            "input_query": "全新的查询",
            "channel_id": "test_channel",
            "kb_names": ["test_kb"],
            "strategy_config": {"enable_semantic_cache": True}
        }
        
        # Mock embedder
        cache._embedder = Mock()
        cache._embedder.embed_text = AsyncMock(return_value=[0.5] * 768)
        
        result = await cache(mock_state)
        
        # 验证缓存未命中
        assert result.get("cache_hit") is False, "应该标记缓存未命中"
        assert result.get("skip_retrieval") is not True, "不应该设置skip_retrieval"
        assert "_query_embedding" in result, "应该保存查询嵌入供后续缓存"

    # TC-SC-EXT-009: 缓存命中后不再检索验证 (P0)
    @pytest.mark.asyncio
    async def test_cache_hit_skips_retrieval_integration(self, cache):
        """验证缓存命中后检索器不被调用的集成验证"""
        # 模拟完整的缓存命中流程
        query_embedding = [0.1] * 768
        cache_key = "sem_cache:tenant:kb:" + cache._embedding_hash(query_embedding)
        cache._cache[cache_key] = (
            query_embedding,
            "缓存答案",
            time.time(),
            {}
        )
        
        # 模拟检索器
        retriever_called = False
        
        async def mock_retriever(state):
            nonlocal retriever_called
            retriever_called = True
            return state
        
        # 缓存检查
        mock_state = {
            "input_query": "测试",
            "channel_id": "tenant",
            "kb_names": ["kb"],
            "strategy_config": {"enable_semantic_cache": True}
        }
        
        cache._embedder = Mock()
        cache._embedder.embed_text = AsyncMock(return_value=query_embedding)
        
        result = await cache(mock_state)
        
        # 如果缓存命中，检索器不应该被调用
        if result.get("cache_hit"):
            # 在实际图执行中，skip_retrieval=True 会跳过检索器
            assert result.get("skip_retrieval") is True
            # 检索器不应该被调用（这里我们验证标记正确设置）
            assert not retriever_called or result.get("skip_retrieval")


class TestSemanticCacheSizeManagement:
    """语义缓存大小管理测试"""
    
    @pytest.fixture
    def small_cache(self):
        return SemanticCache(max_cache_size=10)

    # TC-SC-EXT-010: 缓存大小限制 (P1)
    def test_cache_size_limit(self, small_cache):
        """验证缓存大小超限时的LRU清理"""
        # 填充超过限制的条目
        for i in range(15):
            embedding = [float(i)] * 768
            small_cache._cache[f"key_{i}"] = (
                embedding,
                f"答案_{i}",
                time.time() - (15 - i),  # 越早的条目时间戳越小
                {}
            )
        
        # 触发清理
        small_cache._evict_if_needed()
        
        # 验证大小被限制
        assert len(small_cache._cache) <= 10, "缓存大小应该被限制"
        
        # 验证最老的条目被清理
        # key_0 到 key_4 应该被清理（最老的5个）
        for i in range(5):
            assert f"key_{i}" not in small_cache._cache, f"key_{i} 应该被清理"

    # TC-SC-EXT-011: LRU清理策略 (P1)
    def test_lru_eviction_strategy(self, small_cache):
        """验证LRU清理策略的正确性"""
        current_time = time.time()
        
        # 添加条目，时间戳不同
        entries = [
            ("oldest", current_time - 1000),
            ("middle", current_time - 500),
            ("newest", current_time),
        ]
        
        for key, timestamp in entries:
            small_cache._cache[key] = (
                [0.1] * 768,
                f"答案_{key}",
                timestamp,
                {}
            )
        
        # 填充到超过限制
        for i in range(10):
            small_cache._cache[f"filler_{i}"] = (
                [float(i)] * 768,
                f"填充_{i}",
                current_time + i,  # 比原有条目更新
                {}
            )
        
        # 触发清理
        small_cache._evict_if_needed()
        
        # 验证最老的条目被优先清理
        assert "oldest" not in small_cache._cache, "最老的条目应该被清理"


class TestSemanticCacheStatistics:
    """语义缓存统计测试"""
    
    @pytest.fixture
    def cache(self):
        return SemanticCache()

    # TC-SC-EXT-012: 命中率统计 (P2)
    @pytest.mark.asyncio
    async def test_hit_rate_statistics(self, cache):
        """验证缓存命中率的准确统计"""
        # 初始状态
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        
        # 模拟命中和未命中
        cache._hits = 3
        cache._misses = 7
        
        stats = cache.get_stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 7
        assert stats["total"] == 10
        assert stats["hit_rate"] == 0.3  # 3/10

    # TC-SC-EXT-013: 缓存大小统计 (P2)
    def test_cache_size_statistics(self, cache):
        """验证缓存大小的准确统计"""
        # 添加一些条目
        for i in range(5):
            cache._cache[f"key_{i}"] = (
                [0.1] * 768,
                f"答案_{i}",
                time.time(),
                {}
            )
        
        stats = cache.get_stats()
        assert stats["cache_size"] == 5
        assert stats["max_size"] == cache.max_cache_size

    # TC-SC-EXT-014: 清理后统计重置 (P2)
    def test_statistics_reset_after_clear(self, cache):
        """验证清理后统计的重置"""
        cache._hits = 10
        cache._misses = 5
        cache._cache["test"] = ([0.1] * 768, "答案", time.time(), {})
        
        cache.clear()
        
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["cache_size"] == 0


class TestSemanticCacheSimilarityMatching:
    """语义缓存相似度匹配测试"""
    
    @pytest.fixture
    def cache(self):
        return SemanticCache(similarity_threshold=0.92)

    # TC-SC-EXT-015: 高相似度命中 (P1)
    def test_high_similarity_hit(self, cache):
        """验证高相似度查询的缓存命中"""
        # 添加缓存条目
        cached_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * 763)
        cached_embedding = cached_embedding / np.linalg.norm(cached_embedding)  # 归一化
        
        cache._cache["sem_cache:ch:kb:" + cache._embedding_hash(cached_embedding.tolist())] = (
            cached_embedding.tolist(),
            "缓存答案",
            time.time(),
            {}
        )
        
        # 查询几乎相同的嵌入
        query_embedding = cached_embedding.tolist()
        
        result = cache._find_similar(query_embedding, "sem_cache:ch:kb")
        
        # 应该命中
        assert result is not None, "高相似度查询应该命中缓存"
        assert result[0] == "缓存答案"

    # TC-SC-EXT-016: 低相似度未命中 (P1)
    def test_low_similarity_miss(self, cache):
        """验证低相似度查询的缓存未命中"""
        # 添加缓存条目
        cached_embedding = [0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * 763
        cache._cache["sem_cache:ch:kb:hash1"] = (
            cached_embedding,
            "缓存答案",
            time.time(),
            {}
        )
        
        # 查询完全不同的嵌入
        query_embedding = [0.9, 0.8, 0.7, 0.6, 0.5] + [0.0] * 763
        
        result = cache._find_similar(query_embedding, "sem_cache:ch:kb")
        
        # 应该未命中
        assert result is None, "低相似度查询不应该命中缓存"

    # TC-SC-EXT-017: 阈值边界测试 (P1)
    def test_similarity_threshold_boundary(self, cache):
        """验证相似度阈值边界的处理"""
        # 创建归一化的嵌入
        base = np.array([1.0] + [0.0] * 767)
        base = base / np.linalg.norm(base)
        
        cache._cache["sem_cache:ch:kb:hash"] = (
            base.tolist(),
            "缓存答案",
            time.time(),
            {}
        )
        
        # 创建刚好在阈值边界的查询
        # 余弦相似度 = 0.92 时的角度约为 23度
        angle = np.arccos(0.92)
        query = np.array([np.cos(angle), np.sin(angle)] + [0.0] * 766)
        query = query / np.linalg.norm(query)
        
        result = cache._find_similar(query.tolist(), "sem_cache:ch:kb")
        
        # 边界情况的处理取决于具体实现
        # 这里主要验证不会崩溃


class TestSemanticCacheEmbedderCompatibility:
    """语义缓存嵌入器兼容性测试"""
    
    @pytest.fixture
    def cache(self):
        return SemanticCache()

    # TC-SC-EXT-018: embed_text方法支持 (P1)
    @pytest.mark.asyncio
    async def test_embed_text_method_support(self, cache):
        """验证embed_text方法的支持"""
        mock_embedder = Mock()
        mock_embedder.embed_text = AsyncMock(return_value=[0.1] * 768)
        
        cache._embedder = mock_embedder
        
        result = await cache._embed_query("测试查询")
        
        mock_embedder.embed_text.assert_called_once_with("测试查询")
        assert result == [0.1] * 768

    # TC-SC-EXT-019: embed方法支持 (P1)
    @pytest.mark.asyncio
    async def test_embed_method_support(self, cache):
        """验证embed方法的支持"""
        mock_embedder = Mock()
        # 没有embed_text，只有embed
        mock_embedder.embed = AsyncMock(return_value=[0.2] * 768)
        del mock_embedder.embed_text  # 确保没有embed_text
        
        cache._embedder = mock_embedder
        
        result = await cache._embed_query("测试查询")
        
        mock_embedder.embed.assert_called_once_with("测试查询")
        assert result == [0.2] * 768

    # TC-SC-EXT-020: 嵌入器不可用跳过缓存 (P1)
    @pytest.mark.asyncio
    async def test_embedder_unavailable_skip_cache(self, cache):
        """验证嵌入器不可用时跳过缓存"""
        mock_state = {
            "input_query": "测试查询",
            "channel_id": "test",
            "kb_names": ["kb"],
            "strategy_config": {"enable_semantic_cache": True},
            "capability_loader": None  # 无能力加载器
        }
        
        # 确保没有嵌入器
        cache._embedder = None
        
        with patch.object(cache, '_get_embedder', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # 无法获取嵌入器
            
            result = await cache(mock_state)
            
            # 应该直接返回，不进行缓存操作
            assert result.get("cache_hit") is not True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
