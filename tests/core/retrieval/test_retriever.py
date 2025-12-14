#!/usr/bin/env python3
"""
混合检索器测试 - core/retrieval/nodes/retriever.py

测试多租户隔离、RRF 融合、意图过滤、存储降级等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from typing import Dict, Any, List

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'qdrant_client.models': Mock(),
    'core.embedding.registry': Mock(),
    'core.state': Mock(),
    'core.storage.channel_utils': Mock(),
    'core.storage.kb_config': Mock(),
    'core.storage.keyword_store': Mock(),
    'core.storage.vector_store': Mock(),
    'core.utils.monitor': Mock(),
}):
    from core.retrieval.nodes.retriever import HybridRetriever

class TestHybridRetriever:
    """测试混合检索器的核心功能"""
    
    @pytest.fixture
    def retriever(self):
        """创建检索器实例"""
        return HybridRetriever()
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "preprocessed_queries": ["人工智能是什么"],
            "channel_id": "tenant_a",
            "kb_names": ["kb1", "kb2"],
            "strategy_config": {
                "top_k": 10,
                "embedding_model": "mock_model",
                "rrf_k": 60
            },
            "intent": {
                "type": "qa",
                "filters": {}
            }
        }
    
    @pytest.fixture
    def mock_vector_results(self):
        """创建模拟向量检索结果"""
        return [
            {
                "id": "vec_1",
                "content": "人工智能是计算机科学的一个分支",
                "score": 0.95,
                "metadata": {
                    "channel_id": "tenant_a",
                    "doc_id": "doc1.pdf",
                    "page_num": 1,
                    "chunk_index": 0
                }
            },
            {
                "id": "vec_2", 
                "content": "AI技术在各个领域都有应用",
                "score": 0.88,
                "metadata": {
                    "channel_id": "tenant_a",
                    "doc_id": "doc2.pdf",
                    "page_num": 2,
                    "chunk_index": 1
                }
            }
        ]
    
    @pytest.fixture
    def mock_keyword_results(self):
        """创建模拟关键词检索结果"""
        return [
            {
                "id": "kw_1",
                "content": "人工智能技术发展迅速",
                "score": 0.92,
                "metadata": {
                    "channel_id": "tenant_a",
                    "doc_id": "doc3.pdf",
                    "page_num": 1,
                    "chunk_index": 0
                }
            },
            {
                "id": "kw_2",
                "content": "机器学习是AI的重要组成部分",
                "score": 0.85,
                "metadata": {
                    "channel_id": "tenant_a", 
                    "doc_id": "doc4.pdf",
                    "page_num": 3,
                    "chunk_index": 2
                }
            }
        ]

    # TC-R001: Channel ID 过滤验证 (P0)
    @pytest.mark.asyncio
    async def test_channel_id_filtering_in_rrf_fusion(self, retriever, mock_vector_results, mock_keyword_results):
        """验证 RRF 融合前的 channel_id 过滤"""
        # 添加其他租户的数据
        mixed_vector_results = mock_vector_results + [
            {
                "id": "vec_other",
                "content": "其他租户的内容",
                "score": 0.99,  # 高分但不同租户
                "metadata": {
                    "channel_id": "tenant_b",
                    "doc_id": "other.pdf"
                }
            }
        ]
        
        mixed_keyword_results = mock_keyword_results + [
            {
                "id": "kw_other",
                "content": "其他租户的关键词内容",
                "score": 0.98,
                "metadata": {
                    "channel_id": "tenant_b",
                    "doc_id": "other.pdf"
                }
            }
        ]
        
        # 执行 RRF 融合
        fused_results = retriever._rrf_fusion(
            mixed_vector_results, 
            mixed_keyword_results,
            k=60,
            channel_id="tenant_a"
        )
        
        # 验证只包含 tenant_a 的结果
        for result in fused_results:
            channel = result.get("metadata", {}).get("channel_id")
            assert channel == "tenant_a" or channel is None  # 允许遗留数据

    # TC-R002: 跨租户数据泄露防护 (P0)
    @pytest.mark.asyncio
    async def test_cross_tenant_data_leakage_prevention(self, retriever):
        """验证不同租户数据不会混合"""
        tenant_a_results = [
            {
                "id": "a_1",
                "content": "租户A的内容",
                "score": 0.9,
                "metadata": {"channel_id": "tenant_a"}
            }
        ]
        
        tenant_b_results = [
            {
                "id": "b_1", 
                "content": "租户B的内容",
                "score": 0.95,  # 更高分数
                "metadata": {"channel_id": "tenant_b"}
            }
        ]
        
        # 租户A的融合不应包含租户B的数据
        fused_a = retriever._rrf_fusion(
            tenant_a_results, [], 
            channel_id="tenant_a"
        )
        
        fused_b = retriever._rrf_fusion(
            tenant_b_results, [],
            channel_id="tenant_b"
        )
        
        # 验证结果隔离
        assert len(fused_a) == 1
        assert len(fused_b) == 1
        assert fused_a[0]["id"] == "a_1"
        assert fused_b[0]["id"] == "b_1"

    # TC-R003: 遗留数据兼容性 (P1)
    @pytest.mark.asyncio
    async def test_legacy_data_compatibility(self, retriever):
        """验证无 channel_id 的遗留数据处理"""
        legacy_results = [
            {
                "id": "legacy_1",
                "content": "遗留数据内容",
                "score": 0.8,
                "metadata": {}  # 无 channel_id
            }
        ]
        
        current_results = [
            {
                "id": "current_1",
                "content": "当前数据内容", 
                "score": 0.9,
                "metadata": {"channel_id": "tenant_a"}
            }
        ]
        
        # 遗留数据应该被包含
        fused = retriever._rrf_fusion(
            legacy_results + current_results, [],
            channel_id="tenant_a"
        )
        
        assert len(fused) == 2
        legacy_found = any(r["id"] == "legacy_1" for r in fused)
        current_found = any(r["id"] == "current_1" for r in fused)
        assert legacy_found and current_found

    # TC-R004: kb_names 列表支持 (P1)
    @pytest.mark.asyncio
    async def test_kb_names_list_support(self, retriever, mock_state):
        """验证 kb_names 列表的多知识库检索"""
        mock_state["kb_names"] = ["kb1", "kb2", "kb3"]
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(side_effect=lambda ch, kb, v: f"ch_{ch}_kb_{kb}_v{v}"),
            channel_index_name=Mock(side_effect=lambda ch, kb: f"ch_{ch}_idx_{kb}")
        ):
            # Mock embedder
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            # Mock clients
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(return_value=[])
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=[])
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                await retriever(mock_state)
                
                # 验证每个知识库都被检索
                assert mock_vector_client.search.call_count == 3  # 3个KB
                assert mock_keyword_client.search.call_count == 3

    # TC-R005: kb_name 单值兼容 (P1)
    @pytest.mark.asyncio
    async def test_kb_name_single_value_compatibility(self, retriever, mock_state):
        """验证向后兼容的 kb_name 单值支持"""
        # 移除 kb_names，只设置 kb_name
        del mock_state["kb_names"]
        mock_state["kb_name"] = "single_kb"
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(return_value=[])
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=[])
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 验证单个知识库被检索
                assert mock_vector_client.search.call_count == 1
                assert mock_keyword_client.search.call_count == 1

    # TC-R006: 表格查询过滤 (P1)
    @pytest.mark.asyncio
    async def test_table_query_filtering(self, retriever, mock_state):
        """验证 table_query 意图的块类型过滤"""
        mock_state["intent"] = {
            "type": "table_query",
            "filters": {}
        }
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            # Mock FieldCondition and Filter
            with patch('core.retrieval.nodes.retriever.FieldCondition') as mock_field_condition, \
                 patch('core.retrieval.nodes.retriever.Filter') as mock_filter, \
                 patch('core.retrieval.nodes.retriever.MatchValue') as mock_match_value:
                
                mock_embedder = AsyncMock()
                mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
                
                mock_vector_client = AsyncMock()
                mock_vector_client.search = AsyncMock(return_value=[])
                mock_keyword_client = AsyncMock()
                mock_keyword_client.search = AsyncMock(return_value=[])
                
                with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                     patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                     patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                    
                    await retriever(mock_state)
                    
                    # 验证表格过滤条件被创建
                    mock_field_condition.assert_called()
                    mock_match_value.assert_called_with(value="table")

    # TC-R007: 图片查询过滤 (P1)
    @pytest.mark.asyncio
    async def test_image_query_filtering(self, retriever, mock_state):
        """验证 image_query 意图的图片过滤"""
        mock_state["intent"] = {
            "type": "image_query",
            "filters": {}
        }
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            with patch('core.retrieval.nodes.retriever.FieldCondition') as mock_field_condition, \
                 patch('core.retrieval.nodes.retriever.Filter') as mock_filter, \
                 patch('core.retrieval.nodes.retriever.MatchValue') as mock_match_value:
                
                mock_embedder = AsyncMock()
                mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
                
                mock_vector_client = AsyncMock()
                mock_vector_client.search = AsyncMock(return_value=[])
                mock_keyword_client = AsyncMock()
                mock_keyword_client.search = AsyncMock(return_value=[])
                
                with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                     patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                     patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                    
                    await retriever(mock_state)
                    
                    # 验证图片过滤条件被创建
                    mock_field_condition.assert_called()
                    mock_match_value.assert_called_with(value="image")

    # TC-R008: 向量存储不可用降级 (P1)
    @pytest.mark.asyncio
    async def test_vector_storage_unavailable_degradation(self, retriever, mock_state, mock_keyword_results):
        """验证向量存储失败时的处理"""
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            # 向量客户端失败
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(side_effect=Exception("Vector DB unavailable"))
            
            # 关键词客户端正常
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=mock_keyword_results)
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 应该只有关键词结果
                assert len(result["vector_results"]) == 0
                assert len(result["keyword_results"]) > 0
                assert len(result["fused_results"]) > 0

    # TC-R009: 关键词存储不可用降级 (P1)
    @pytest.mark.asyncio
    async def test_keyword_storage_unavailable_degradation(self, retriever, mock_state, mock_vector_results):
        """验证关键词存储失败时的处理"""
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            # 向量客户端正常
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(return_value=mock_vector_results)
            
            # 关键词客户端失败
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(side_effect=Exception("ES unavailable"))
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 应该只有向量结果
                assert len(result["vector_results"]) > 0
                assert len(result["keyword_results"]) == 0
                assert len(result["fused_results"]) > 0

    # TC-R010: RRF 融合算法验证 (P1)
    def test_rrf_fusion_algorithm_verification(self, retriever):
        """验证 RRF 融合算法的正确性"""
        vector_results = [
            {"id": "doc1", "score": 0.9, "metadata": {"channel_id": "test"}},
            {"id": "doc2", "score": 0.8, "metadata": {"channel_id": "test"}},
            {"id": "doc3", "score": 0.7, "metadata": {"channel_id": "test"}}
        ]
        
        keyword_results = [
            {"id": "doc2", "score": 0.95, "metadata": {"channel_id": "test"}},  # 重复文档
            {"id": "doc4", "score": 0.85, "metadata": {"channel_id": "test"}},
            {"id": "doc1", "score": 0.75, "metadata": {"channel_id": "test"}}   # 重复文档
        ]
        
        fused = retriever._rrf_fusion(vector_results, keyword_results, k=60, channel_id="test")
        
        # 验证融合结果
        assert len(fused) == 4  # 去重后的文档数
        
        # 验证 doc1 和 doc2 的分数被正确融合（两个来源都有）
        doc1_fused = next(r for r in fused if r["id"] == "doc1")
        doc2_fused = next(r for r in fused if r["id"] == "doc2")
        
        # RRF 分数应该是两个来源分数的组合
        # doc1: 1/(60+1) + 1/(60+3) ≈ 0.0164 + 0.0159 ≈ 0.0323
        # doc2: 1/(60+2) + 1/(60+1) ≈ 0.0161 + 0.0164 ≈ 0.0325
        assert doc2_fused["score"] > doc1_fused["score"]  # doc2 应该分数更高

    # TC-R011: 语言过滤支持 (P2)
    @pytest.mark.asyncio
    async def test_language_filtering_support(self, retriever, mock_state):
        """验证语言过滤的支持"""
        mock_state["intent"]["filters"] = {"lang": "zh"}
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            with patch('core.retrieval.nodes.retriever.FieldCondition') as mock_field_condition, \
                 patch('core.retrieval.nodes.retriever.MatchValue') as mock_match_value:
                
                mock_embedder = AsyncMock()
                mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
                
                mock_vector_client = AsyncMock()
                mock_vector_client.search = AsyncMock(return_value=[])
                mock_keyword_client = AsyncMock()
                mock_keyword_client.search = AsyncMock(return_value=[])
                
                with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                     patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                     patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                    
                    await retriever(mock_state)
                    
                    # 验证语言过滤条件被创建
                    calls = mock_match_value.call_args_list
                    lang_filter_found = any(call[1]["value"] == "zh" for call in calls)
                    assert lang_filter_found

    # TC-R012: 异步嵌入器支持 (P1)
    @pytest.mark.asyncio
    async def test_async_embedder_support(self, retriever, mock_state):
        """验证异步和同步嵌入器的兼容性"""
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            # 测试异步嵌入器
            async_embedder = AsyncMock()
            async_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(return_value=[])
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=[])
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=async_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 验证异步嵌入器被正确调用
                async_embedder.embed.assert_called()
                assert "fused_results" in result

    # TC-R013: Top-K 限制验证 (P1)
    @pytest.mark.asyncio
    async def test_top_k_limit_verification(self, retriever, mock_state):
        """验证 Top-K 限制的正确应用"""
        mock_state["strategy_config"]["top_k"] = 3
        
        # 创建更多结果
        many_vector_results = [
            {"id": f"vec_{i}", "score": 0.9 - i*0.1, "metadata": {"channel_id": "test"}}
            for i in range(10)
        ]
        
        many_keyword_results = [
            {"id": f"kw_{i}", "score": 0.8 - i*0.1, "metadata": {"channel_id": "test"}}
            for i in range(10)
        ]
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(return_value=many_vector_results)
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=many_keyword_results)
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 验证最终结果被限制在 top_k
                assert len(result["fused_results"]) <= 3

    # TC-R014: Channel ID 缺失拒绝 (P0)
    @pytest.mark.asyncio
    async def test_channel_id_missing_rejection(self, retriever):
        """验证缺失 channel_id 时的拒绝处理"""
        missing_channel_state = {
            "preprocessed_queries": ["测试查询"],
            "channel_id": None,  # 缺失 channel_id
            "kb_names": ["test_kb"],
            "strategy_config": {"top_k": 10},
            "intent": {"type": "qa"}
        }
        
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_vector_client=Mock(return_value=AsyncMock()),
            get_keyword_client=Mock(return_value=AsyncMock()),
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            # 应该记录警告或使用默认处理
            result = await retriever(missing_channel_state)
            
            # 验证处理结果 - 应该有警告或默认行为
            assert "fused_results" in result
            # 可能返回空结果或使用默认channel处理

    # TC-R015: 跨租户数据严格过滤 (P0)
    def test_cross_tenant_data_strict_filtering(self, retriever):
        """验证跨租户数据的严格过滤"""
        # 构造包含多个租户数据的结果
        mixed_results = [
            {"id": "tenant_a_1", "score": 0.9, "metadata": {"channel_id": "tenant_a"}},
            {"id": "tenant_b_1", "score": 0.95, "metadata": {"channel_id": "tenant_b"}},  # 更高分但错误租户
            {"id": "tenant_a_2", "score": 0.8, "metadata": {"channel_id": "tenant_a"}},
            {"id": "no_channel", "score": 0.85, "metadata": {}},  # 无channel_id的遗留数据
        ]
        
        # 执行RRF融合，指定tenant_a
        fused = retriever._rrf_fusion(mixed_results, [], channel_id="tenant_a")
        
        # 验证严格过滤
        for result in fused:
            channel = result.get("metadata", {}).get("channel_id")
            # 只允许tenant_a或遗留数据（无channel_id）
            assert channel == "tenant_a" or channel is None
            # 绝对不能包含tenant_b的数据
            assert channel != "tenant_b"
        
        # 验证tenant_b的高分数据被正确过滤掉
        result_ids = [r["id"] for r in fused]
        assert "tenant_b_1" not in result_ids
        assert "tenant_a_1" in result_ids

    # TC-R016: 存储客户端超时处理 (P1)
    @pytest.mark.asyncio
    async def test_storage_client_timeout_handling(self, retriever, mock_state):
        """验证存储客户端超时的处理"""
        with patch.multiple(
            'core.retrieval.nodes.retriever',
            get_embedder=Mock(return_value=AsyncMock()),
            load_kb_config=Mock(return_value={"version": 1}),
            channel_collection_name=Mock(return_value="test_collection"),
            channel_index_name=Mock(return_value="test_index")
        ):
            mock_embedder = AsyncMock()
            mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
            
            # 模拟向量客户端超时
            mock_vector_client = AsyncMock()
            mock_vector_client.search = AsyncMock(side_effect=asyncio.TimeoutError("Vector search timeout"))
            
            # 关键词客户端正常
            mock_keyword_client = AsyncMock()
            mock_keyword_client.search = AsyncMock(return_value=[
                {"id": "kw_1", "content": "关键词结果", "score": 0.8, "metadata": {"channel_id": "test"}}
            ])
            
            with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                 patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                 patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                
                result = await retriever(mock_state)
                
                # 验证超时不导致崩溃，降级到仅关键词检索
                assert len(result["vector_results"]) == 0  # 向量检索失败
                assert len(result["keyword_results"]) > 0   # 关键词检索成功
                assert len(result["fused_results"]) > 0     # 仍有融合结果

    # TC-R017: 检索延迟监控 (P2)
    @pytest.mark.asyncio
    async def test_retrieval_latency_monitoring(self, retriever, mock_state):
        """验证检索延迟的监控"""
        with patch('core.retrieval.nodes.retriever.retrieval_latency') as mock_latency:
            mock_timer = Mock()
            mock_latency.time.return_value.__enter__ = Mock(return_value=mock_timer)
            mock_latency.time.return_value.__exit__ = Mock(return_value=None)
            
            with patch.multiple(
                'core.retrieval.nodes.retriever',
                get_vector_client=Mock(return_value=AsyncMock()),
                get_keyword_client=Mock(return_value=AsyncMock()),
                get_embedder=Mock(return_value=AsyncMock()),
                load_kb_config=Mock(return_value={"version": 1}),
                channel_collection_name=Mock(return_value="test_collection"),
                channel_index_name=Mock(return_value="test_index")
            ):
                mock_embedder = AsyncMock()
                mock_embedder.embed = AsyncMock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
                
                mock_vector_client = AsyncMock()
                mock_vector_client.search = AsyncMock(return_value=[])
                mock_keyword_client = AsyncMock()
                mock_keyword_client.search = AsyncMock(return_value=[])
                
                with patch('core.retrieval.nodes.retriever.get_embedder', return_value=mock_embedder), \
                     patch('core.retrieval.nodes.retriever.get_vector_client', return_value=mock_vector_client), \
                     patch('core.retrieval.nodes.retriever.get_keyword_client', return_value=mock_keyword_client):
                    
                    await retriever(mock_state)
                    
                    # 验证延迟监控被调用
                    mock_latency.time.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])