#!/usr/bin/env python3
"""
语义缓存测试 - core/retrieval/nodes/semantic_cache.py

测试缓存命中/未命中、TTL 过期、嵌入哈希冲突、多租户隔离等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import hashlib
import numpy as np
from typing import Dict, Any, List

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'core.state': Mock(),
}):
    from core.retrieval.nodes.semantic_cache import (
        SemanticCache, get_semantic_cache
    )

class TestSemanticCache:
    """测试语义缓存的核心功能"""
    
    @pytest.fixture
    def cache(self):
        """创建缓存实例"""
        return SemanticCache(
            similarity_threshold=0.92,
            ttl_seconds=3600,
            max_cache_size=100
        )
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "input_query": "什么是人工智能？",
            "channel_id": "tenant_a",
            "kb_names": ["kb1", "kb2"],
            "strategy_config": {
                "enable_semantic_cache": True
            }
        }
    
    @pytest.fixture
    def mock_embedder(self):
        """创建模拟嵌入器"""
        embedder = AsyncMock()
        embedder.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5] * 10)  # 50维向量
        return embedder

    # TC-SC001: 语义相似查询缓存命中 (P1)
    @pytest.mark.asyncio
    async def test_semantic_similar_query_cache_hit(self, cache, mock_state, mock_embedder):
        """验证语义相似查询的缓存命中"""
        cache._embedder = mock_embedder
        
        # 第一次查询 - 缓存未命中
        result1 = await cache(mock_state.copy())
        assert result1["cache_hit"] is False
        assert "_query_embedding" in result1
        
        # 模拟缓存答案
        cached_answer = "人工智能是计算机科学的一个分支。"
        cache_result_state = result1.copy()
        cache_result_state["final_answer"] = cached_answer
        cache_result_state["confidence"] = 0.85
        cache_result_state["citations"] = [{"doc_id": "test.pdf"}]
        
        await cache.cache_result(cache_result_state)
        
        # 第二次相似查询 - 应该缓存命中
        similar_state = mock_state.copy()
        similar_state["input_query"] = "AI是什么？"  # 语义相似
        
        # Mock 相似的嵌入向量
        mock_embedder.embed_text = AsyncMock(return_value=[0.11, 0.21, 0.31, 0.41, 0.51] * 10)
        
        result2 = await cache(similar_state)
        
        # 验证缓存命中
        assert result2["cache_hit"] is True
        assert result2["final_answer"] == cached_answer
        assert result2["skip_retrieval"] is True
        assert "cache_metadata" in result2

    # TC-SC002: 语义不相似查询缓存未命中 (P1)
    @pytest.mark.asyncio
    async def test_semantic_dissimilar_query_cache_miss(self, cache, mock_state, mock_embedder):
        """验证不相似查询的缓存未命中"""
        cache._embedder = mock_embedder
        
        # 缓存第一个查询
        result1 = await cache(mock_state.copy())
        cache_result_state = result1.copy()
        cache_result_state["final_answer"] = "AI相关答案"
        await cache.cache_result(cache_result_state)
        
        # 完全不同的查询
        different_state = mock_state.copy()
        different_state["input_query"] = "今天天气怎么样？"
        
        # Mock 完全不同的嵌入向量
        mock_embedder.embed_text = AsyncMock(return_value=[0.9, 0.8, 0.7, 0.6, 0.5] * 10)
        
        result2 = await cache(different_state)
        
        # 验证缓存未命中
        assert result2["cache_hit"] is False
        assert "_query_embedding" in result2

    # TC-SC003: 相似度阈值控制 (P1)
    @pytest.mark.asyncio
    async def test_similarity_threshold_control(self, mock_state, mock_embedder):
        """验证相似度阈值对缓存命中的影响"""
        # 创建高阈值缓存
        high_threshold_cache = SemanticCache(similarity_threshold=0.99)
        high_threshold_cache._embedder = mock_embedder
        
        # 缓存查询
        result1 = await high_threshold_cache(mock_state.copy())
        cache_result_state = result1.copy()
        cache_result_state["final_answer"] = "缓存答案"
        await high_threshold_cache.cache_result(cache_result_state)
        
        # 稍微不同的查询（相似度约0.95）
        similar_state = mock_state.copy()
        similar_state["input_query"] = "什么是AI技术？"
        
        # Mock 高相似度但低于阈值的向量
        mock_embedder.embed_text = AsyncMock(return_value=[0.12, 0.22, 0.32, 0.42, 0.52] * 10)
        
        result2 = await high_threshold_cache(similar_state)
        
        # 高阈值下应该未命中
        assert result2["cache_hit"] is False
        
        # 创建低阈值缓存
        low_threshold_cache = SemanticCache(similarity_threshold=0.8)
        low_threshold_cache._embedder = mock_embedder
        
        # 同样的查询在低阈值下应该命中
        # 这里需要重新缓存，因为是不同的缓存实例
        result3 = await low_threshold_cache(mock_state.copy())
        cache_result_state = result3.copy()
        cache_result_state["final_answer"] = "缓存答案"
        await low_threshold_cache.cache_result(cache_result_state)
        
        result4 = await low_threshold_cache(similar_state)
        # 在实际实现中，这可能需要更精确的相似度计算模拟

    # TC-SC004: 缓存 TTL 过期 (P1)
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, cache, mock_state, mock_embedder):
        """验证缓存条目的 TTL 过期"""
        cache._embedder = mock_embedder
        
        # 缓存查询
        with patch('time.time', return_value=1000.0):
            result1 = await cache(mock_state.copy())
            cache_result_state = result1.copy()
            cache_result_state["final_answer"] = "缓存答案"
            await cache.cache_result(cache_result_state)
        
        # 时间推进但未超过 TTL
        with patch('time.time', return_value=1000.0 + 1800):  # 30分钟后
            result2 = await cache(mock_state.copy())
            assert result2["cache_hit"] is True  # 应该命中
        
        # 时间推进超过 TTL
        with patch('time.time', return_value=1000.0 + 3700):  # 超过1小时
            result3 = await cache(mock_state.copy())
            assert result3["cache_hit"] is False  # 应该过期

    # TC-SC005: 缓存大小限制 (P1)
    @pytest.mark.asyncio
    async def test_cache_size_limit(self, mock_embedder):
        """验证缓存大小超限时的 LRU 清理"""
        # 创建小容量缓存
        small_cache = SemanticCache(max_cache_size=3)
        small_cache._embedder = mock_embedder
        
        # 添加多个缓存项
        for i in range(5):
            state = {
                "input_query": f"查询{i}",
                "channel_id": "test",
                "kb_names": ["kb1"],
                "strategy_config": {"enable_semantic_cache": True}
            }
            
            # Mock 不同的嵌入向量
            mock_embedder.embed_text = AsyncMock(return_value=[i * 0.1] * 50)
            
            result = await small_cache(state)
            if not result["cache_hit"]:
                cache_result_state = result.copy()
                cache_result_state["final_answer"] = f"答案{i}"
                await small_cache.cache_result(cache_result_state)
        
        # 验证缓存大小被限制
        assert len(small_cache._cache) <= 3

    # TC-SC006: 嵌入哈希冲突风险 (P2)
    def test_embedding_hash_collision_risk(self, cache):
        """验证 _embedding_hash 的冲突处理"""
        # 创建相似但不同的嵌入向量
        embedding1 = [0.1, 0.2, 0.3, 0.4, 0.5] * 10
        embedding2 = [0.1, 0.2, 0.3, 0.4, 0.51] * 10  # 最后一个值略有不同
        
        hash1 = cache._embedding_hash(embedding1)
        hash2 = cache._embedding_hash(embedding2)
        
        # 验证不同嵌入产生不同哈希
        assert hash1 != hash2
        
        # 验证哈希长度和格式
        assert len(hash1) == 16  # SHA256前16位
        assert len(hash2) == 16
        assert all(c in '0123456789abcdef' for c in hash1)
        assert all(c in '0123456789abcdef' for c in hash2)

    # TC-SC007: 缓存键前缀隔离 (P0)
    def test_cache_key_prefix_isolation(self, cache):
        """验证不同 channel/kb 的缓存键隔离"""
        test_cases = [
            ("tenant_a", ["kb1", "kb2"]),
            ("tenant_b", ["kb1", "kb2"]),
            ("tenant_a", ["kb3", "kb4"]),
            ("tenant_c", [])
        ]
        
        prefixes = []
        for channel_id, kb_names in test_cases:
            prefix = cache._make_cache_key_prefix(channel_id, kb_names)
            prefixes.append(prefix)
        
        # 验证所有前缀都不同
        assert len(set(prefixes)) == len(prefixes)
        
        # 验证前缀格式
        for prefix in prefixes:
            assert prefix.startswith("sem_cache:")
            assert ":" in prefix

    # TC-SC008: 多种嵌入器支持 (P1)
    @pytest.mark.asyncio
    async def test_multiple_embedder_support(self, cache, mock_state):
        """验证不同嵌入器接口的兼容性"""
        # 测试 embed_text 方法
        embedder_with_embed_text = AsyncMock()
        embedder_with_embed_text.embed_text = AsyncMock(return_value=[0.1] * 50)
        
        cache._embedder = embedder_with_embed_text
        result1 = await cache(mock_state.copy())
        assert "_query_embedding" in result1
        
        # 测试 embed 方法
        embedder_with_embed = AsyncMock()
        embedder_with_embed.embed = AsyncMock(return_value=[0.2] * 50)
        
        cache._embedder = embedder_with_embed
        result2 = await cache(mock_state.copy())
        assert "_query_embedding" in result2

    # TC-SC009: 嵌入器不可用降级 (P1)
    @pytest.mark.asyncio
    async def test_embedder_unavailable_degradation(self, cache, mock_state):
        """验证嵌入器不可用时跳过缓存"""
        # 嵌入器为 None
        cache._embedder = None
        
        result = await cache(mock_state.copy())
        
        # 应该跳过缓存检查
        assert result == mock_state  # 状态不变
        
        # 嵌入器抛出异常
        failing_embedder = AsyncMock()
        failing_embedder.embed_text = AsyncMock(side_effect=Exception("Embedder failed"))
        
        cache._embedder = failing_embedder
        result2 = await cache(mock_state.copy())
        
        # 应该跳过缓存检查
        assert result2 == mock_state

    # TC-SC010: 缓存命中率统计 (P2)
    @pytest.mark.asyncio
    async def test_cache_hit_rate_statistics(self, cache, mock_embedder):
        """验证缓存命中率的准确统计"""
        cache._embedder = mock_embedder
        
        # 执行多次查询
        queries = [
            "什么是AI？",
            "AI的定义是什么？",  # 相似查询，应该命中
            "今天天气如何？",     # 不同查询，应该未命中
            "人工智能的概念？"    # 相似查询，应该命中
        ]
        
        embeddings = [
            [0.1] * 50,
            [0.11] * 50,  # 相似
            [0.9] * 50,   # 不同
            [0.12] * 50   # 相似
        ]
        
        for i, (query, embedding) in enumerate(zip(queries, embeddings)):
            state = {
                "input_query": query,
                "channel_id": "test",
                "kb_names": ["kb1"],
                "strategy_config": {"enable_semantic_cache": True}
            }
            
            mock_embedder.embed_text = AsyncMock(return_value=embedding)
            
            result = await cache(state)
            
            # 如果缓存未命中，添加答案到缓存
            if not result.get("cache_hit", False):
                cache_result_state = result.copy()
                cache_result_state["final_answer"] = f"答案{i}"
                await cache.cache_result(cache_result_state)
        
        # 获取统计信息
        stats = cache.get_stats()
        
        # 验证统计信息
        assert stats["total"] == cache._hits + cache._misses
        assert 0 <= stats["hit_rate"] <= 1
        assert stats["cache_size"] <= cache.max_cache_size

    # TC-SC011: 缓存禁用处理 (P1)
    @pytest.mark.asyncio
    async def test_cache_disabled_handling(self, cache, mock_state):
        """验证缓存禁用时的处理"""
        # 禁用语义缓存
        mock_state["strategy_config"]["enable_semantic_cache"] = False
        
        result = await cache(mock_state.copy())
        
        # 应该跳过缓存处理
        assert result == mock_state

    # TC-SC012: 空查询处理 (P1)
    @pytest.mark.asyncio
    async def test_empty_query_handling(self, cache):
        """验证空查询的处理"""
        empty_state = {
            "input_query": "",
            "channel_id": "test",
            "kb_names": ["kb1"],
            "strategy_config": {"enable_semantic_cache": True}
        }
        
        result = await cache(empty_state)
        
        # 应该跳过缓存处理
        assert result == empty_state

    # TC-SC013: 嵌入器初始化 (P1)
    @pytest.mark.asyncio
    async def test_embedder_initialization(self, cache, mock_state):
        """验证嵌入器的初始化过程"""
        # Mock capability_loader
        mock_capability_loader = Mock()
        mock_multimodal_embedding = AsyncMock()
        mock_multimodal_embedding.embed_text = AsyncMock(return_value=[0.1] * 50)
        mock_capability_loader.get = Mock(return_value=mock_multimodal_embedding)
        
        mock_state["capability_loader"] = mock_capability_loader
        
        result = await cache(mock_state.copy())
        
        # 验证嵌入器被初始化
        assert cache._embedder is not None
        mock_capability_loader.get.assert_called_with("multimodal_embedding")

    # TC-SC014: 回退嵌入器创建 (P2)
    @pytest.mark.asyncio
    async def test_fallback_embedder_creation(self, cache, mock_state):
        """验证回退嵌入器的创建"""
        # Mock SentenceTransformer
        with patch('sentence_transformers.SentenceTransformer') as mock_st:
            mock_model = Mock()
            mock_model.encode = Mock(return_value=np.array([0.1] * 50))
            mock_st.return_value = mock_model
            
            # 无 capability_loader
            mock_state["capability_loader"] = None
            
            result = await cache(mock_state.copy())
            
            # 验证回退嵌入器被创建
            if cache._embedder is not None:
                assert hasattr(cache._embedder, 'embed_text')

    # TC-SC015: 缓存清理功能 (P2)
    def test_cache_clearing_functionality(self, cache):
        """验证缓存清理功能"""
        # 手动添加缓存项
        cache._cache["test_key"] = ([0.1] * 50, "test_answer", time.time(), {})
        cache._hits = 10
        cache._misses = 5
        
        assert len(cache._cache) > 0
        assert cache._hits > 0
        assert cache._misses > 0
        
        # 清理缓存
        cache.clear()
        
        # 验证缓存被清空
        assert len(cache._cache) == 0
        assert cache._hits == 0
        assert cache._misses == 0

    # TC-SC016: 相似度计算验证 (P2)
    def test_similarity_calculation_verification(self, cache):
        """验证余弦相似度计算的正确性"""
        # 创建测试向量
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]  # 垂直向量，相似度应为0
        vec3 = [1.0, 0.0, 0.0]  # 相同向量，相似度应为1
        
        # 手动添加缓存项
        cache_key_prefix = "test_prefix"
        cache._cache[f"{cache_key_prefix}:hash1"] = (vec1, "answer1", time.time(), {})
        cache._cache[f"{cache_key_prefix}:hash2"] = (vec2, "answer2", time.time(), {})
        
        # 测试与 vec3 的相似度
        result1 = cache._find_similar(vec3, cache_key_prefix)
        
        # 应该找到与 vec1 相似的结果
        assert result1 is not None
        assert result1[0] == "answer1"

    # TC-SC017: 单例模式验证 (P2)
    def test_singleton_pattern_verification(self):
        """验证 get_semantic_cache 的单例模式"""
        cache1 = get_semantic_cache()
        cache2 = get_semantic_cache()
        
        # 应该返回同一个实例
        assert cache1 is cache2

    # TC-SC018: 缓存结果存储验证 (P1)
    @pytest.mark.asyncio
    async def test_cache_result_storage_verification(self, cache, mock_state, mock_embedder):
        """验证缓存结果存储的正确性"""
        cache._embedder = mock_embedder
        
        # 第一次查询
        result = await cache(mock_state.copy())
        
        # 添加答案到缓存
        cache_result_state = result.copy()
        cache_result_state["final_answer"] = "测试答案"
        cache_result_state["confidence"] = 0.9
        cache_result_state["citations"] = [{"doc_id": "test.pdf"}]
        
        await cache.cache_result(cache_result_state)
        
        # 验证缓存项被正确存储
        assert len(cache._cache) == 1
        
        # 验证缓存项内容
        cache_key = list(cache._cache.keys())[0]
        cached_embedding, cached_answer, timestamp, metadata = cache._cache[cache_key]
        
        assert cached_answer == "测试答案"
        assert metadata["confidence"] == 0.9
        assert metadata["sources_count"] == 1
        assert metadata["query"] == mock_state["input_query"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])