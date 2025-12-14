#!/usr/bin/env python3
"""
重排序器测试 - core/retrieval/nodes/reranker.py

测试异步包装、阈值过滤、缓存并发安全、置信度计算等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import time
from typing import Dict, Any, List

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'core.reranker.registry': Mock(),
    'core.state': Mock(),
}):
    from core.retrieval.nodes.reranker import (
        CrossEncoderReranker, clear_reranker_cache, _RERANKER_CACHE, _CACHE_TTL
    )

class TestCrossEncoderReranker:
    """测试交叉编码器重排序器的核心功能"""
    
    @pytest.fixture
    def reranker(self):
        """创建重排序器实例"""
        return CrossEncoderReranker()
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "strategy_config": {
                "reranker_provider": "cross_encoder",
                "reranker_model": "ms-marco-MiniLM-L-6-v2",
                "fallback_rerank_models": ["backup-model-1", "backup-model-2"],
                "rerank_threshold": 0.3
            },
            "input_query": "什么是人工智能？",
            "fused_results": [
                {
                    "id": "doc1",
                    "content": "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
                    "score": 0.85,
                    "metadata": {"doc_id": "ai_intro.pdf"}
                },
                {
                    "id": "doc2", 
                    "content": "机器学习是人工智能的一个子领域，专注于算法和统计模型的开发。",
                    "score": 0.78,
                    "metadata": {"doc_id": "ml_basics.pdf"}
                },
                {
                    "id": "doc3",
                    "content": "深度学习使用多层神经网络来模拟人脑的工作方式。",
                    "score": 0.72,
                    "metadata": {"doc_id": "dl_guide.pdf"}
                },
                {
                    "id": "doc4",
                    "content": "这是一个不相关的文档，讲述的是烹饪技巧。",
                    "score": 0.45,
                    "metadata": {"doc_id": "cooking.pdf"}
                }
            ]
        }

    # TC-RR001: 同步重排序器异步包装 (P1)
    @pytest.mark.asyncio
    async def test_sync_reranker_async_wrapping(self, reranker, mock_state):
        """验证同步 reranker.score() 的异步包装"""
        # 清理缓存
        clear_reranker_cache()
        
        # Mock 同步重排序器
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])  # 同步方法
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            result = await reranker(mock_state.copy())
            
            # 验证同步方法被异步包装调用
            mock_sync_reranker.score.assert_called_once()
            
            # 验证重排序结果
            reranked = result["reranked_results"]
            assert len(reranked) == 4  # 所有文档都通过阈值
            assert reranked[0]["rerank_score"] == 0.9
            assert reranked[0]["id"] == "doc1"  # 最高分排在前面

    # TC-RR002: 异步重排序器直接调用 (P1)
    @pytest.mark.asyncio
    async def test_async_reranker_direct_call(self, reranker, mock_state):
        """验证异步 reranker 的直接调用"""
        clear_reranker_cache()
        
        # Mock 异步重排序器
        mock_async_reranker = AsyncMock()
        mock_async_reranker.score = AsyncMock(return_value=[0.8, 0.6, 0.4, 0.1])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_async_reranker
            
            result = await reranker(mock_state.copy())
            
            # 验证异步方法被直接调用
            mock_async_reranker.score.assert_called_once()
            
            # 验证重排序结果
            reranked = result["reranked_results"]
            assert reranked[0]["rerank_score"] == 0.8

    # TC-RR003: 重排序阈值过滤 (P1)
    @pytest.mark.asyncio
    async def test_rerank_threshold_filtering(self, reranker, mock_state):
        """验证低分结果被阈值过滤"""
        clear_reranker_cache()
        
        # 设置较高的阈值
        mock_state["strategy_config"]["rerank_threshold"] = 0.6
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])  # 后两个低于阈值
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            result = await reranker(mock_state.copy())
            
            # 验证只有高于阈值的结果被保留
            reranked = result["reranked_results"]
            assert len(reranked) == 2  # 只有前两个通过阈值
            assert all(doc["rerank_score"] >= 0.6 for doc in reranked)
            assert result["is_relevant"] is True

    # TC-RR004: 空结果处理 (P1)
    @pytest.mark.asyncio
    async def test_empty_results_handling(self, reranker):
        """验证无结果通过阈值时的处理"""
        empty_state = {
            "strategy_config": {
                "reranker_provider": "cross_encoder",
                "reranker_model": "test-model"
            },
            "input_query": "测试查询",
            "fused_results": []
        }
        
        result = await reranker(empty_state)
        
        # 验证空结果处理
        assert result["reranked_results"] == []
        assert result["is_relevant"] is False

    # TC-RR005: 重排序器实例缓存 (P1)
    @pytest.mark.asyncio
    async def test_reranker_instance_caching(self, reranker, mock_state):
        """验证重排序器实例的 TTL 缓存"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            # 第一次调用
            await reranker(mock_state.copy())
            first_call_count = mock_get_reranker.call_count
            
            # 第二次调用相同配置
            await reranker(mock_state.copy())
            second_call_count = mock_get_reranker.call_count
            
            # 应该复用缓存的实例
            assert second_call_count == first_call_count

    # TC-RR006: 缓存 TTL 过期 (P1)
    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, reranker, mock_state):
        """验证缓存过期后重新创建实例"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker, \
             patch('time.time') as mock_time:
            
            mock_get_reranker.return_value = mock_sync_reranker
            
            # 第一次调用
            mock_time.return_value = 1000.0
            await reranker(mock_state.copy())
            first_call_count = mock_get_reranker.call_count
            
            # 模拟时间超过 TTL
            mock_time.return_value = 1000.0 + _CACHE_TTL + 1
            await reranker(mock_state.copy())
            second_call_count = mock_get_reranker.call_count
            
            # 应该创建新实例
            assert second_call_count > first_call_count

    # TC-RR007: 并发缓存安全 (P2)
    @pytest.mark.asyncio
    async def test_concurrent_cache_safety(self, reranker, mock_state):
        """验证并发访问缓存的线程安全"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            # 并发执行多个重排序任务
            tasks = [
                reranker(mock_state.copy())
                for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 所有任务都应该成功完成
            assert len(results) == 10
            for result in results:
                assert "reranked_results" in result
                assert len(result["reranked_results"]) > 0

    # TC-RR008: 检索置信度计算 (P1)
    @pytest.mark.asyncio
    async def test_retrieval_confidence_calculation(self, reranker, mock_state):
        """验证基于重排序分数的置信度计算"""
        clear_reranker_cache()
        
        # 测试不同分数场景
        test_cases = [
            {
                "scores": [0.9, 0.8, 0.7, 0.6],
                "expected_confidence": 0.8  # (0.9 + 0.8 + 0.7) / 3
            },
            {
                "scores": [0.5, 0.4, 0.3],
                "expected_confidence": 0.4  # (0.5 + 0.4 + 0.3) / 3
            },
            {
                "scores": [1.0, 0.9],
                "expected_confidence": 0.95  # (1.0 + 0.9) / 2
            }
        ]
        
        for case in test_cases:
            mock_sync_reranker = Mock()
            mock_sync_reranker.score = Mock(return_value=case["scores"])
            
            with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
                mock_get_reranker.return_value = mock_sync_reranker
                
                # 调整文档数量匹配分数数量
                test_state = mock_state.copy()
                test_state["fused_results"] = test_state["fused_results"][:len(case["scores"])]
                
                result = await reranker(test_state)
                
                # 验证置信度计算
                confidence = result["retrieval_confidence"]
                assert abs(confidence - case["expected_confidence"]) < 0.01

    # TC-RR009: 无结果时置信度为零 (P1)
    @pytest.mark.asyncio
    async def test_zero_confidence_for_no_results(self, reranker):
        """验证无结果时置信度为零"""
        no_results_state = {
            "strategy_config": {
                "reranker_provider": "cross_encoder",
                "reranker_model": "test-model",
                "rerank_threshold": 0.5
            },
            "input_query": "测试查询",
            "fused_results": []
        }
        
        result = await reranker(no_results_state)
        
        assert result["retrieval_confidence"] == 0.0

    # TC-RR010: 重排序器获取失败处理 (P1)
    @pytest.mark.asyncio
    async def test_reranker_acquisition_failure_handling(self, reranker, mock_state):
        """验证重排序器获取失败的处理"""
        clear_reranker_cache()
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.side_effect = Exception("Reranker not available")
            
            # 应该抛出异常或优雅处理
            with pytest.raises(Exception):
                await reranker(mock_state.copy())

    # TC-RR011: 重排序推理失败处理 (P1)
    @pytest.mark.asyncio
    async def test_reranking_inference_failure_handling(self, reranker, mock_state):
        """验证重排序推理异常的处理"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(side_effect=Exception("Inference failed"))
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            # 应该抛出异常或优雅处理
            with pytest.raises(Exception):
                await reranker(mock_state.copy())

    # TC-RR012: 配置变化缓存失效 (P1)
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_config_change(self, reranker):
        """验证配置变化时缓存失效"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            # 第一个配置
            state1 = {
                "strategy_config": {
                    "reranker_provider": "provider1",
                    "reranker_model": "model1",
                    "fallback_rerank_models": []
                },
                "input_query": "测试",
                "fused_results": [
                    {"id": "1", "content": "内容1", "score": 0.8},
                    {"id": "2", "content": "内容2", "score": 0.7}
                ]
            }
            await reranker(state1)
            first_call_count = mock_get_reranker.call_count
            
            # 第二个不同配置
            state2 = {
                "strategy_config": {
                    "reranker_provider": "provider2",
                    "reranker_model": "model2", 
                    "fallback_rerank_models": []
                },
                "input_query": "测试",
                "fused_results": [
                    {"id": "1", "content": "内容1", "score": 0.8},
                    {"id": "2", "content": "内容2", "score": 0.7}
                ]
            }
            await reranker(state2)
            second_call_count = mock_get_reranker.call_count
            
            # 应该创建新实例
            assert second_call_count > first_call_count

    # TC-RR013: 回退模型配置传递 (P1)
    @pytest.mark.asyncio
    async def test_fallback_models_configuration_passing(self, reranker, mock_state):
        """验证回退模型配置的传递"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9, 0.7, 0.5, 0.2])
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            await reranker(mock_state.copy())
            
            # 验证 get_reranker 被正确调用
            mock_get_reranker.assert_called_with(
                provider="cross_encoder",
                model_id="ms-marco-MiniLM-L-6-v2",
                fallback_models=["backup-model-1", "backup-model-2"]
            )

    # TC-RR014: 缓存键生成验证 (P2)
    @pytest.mark.asyncio
    async def test_cache_key_generation_verification(self, reranker):
        """验证缓存键的正确生成"""
        clear_reranker_cache()
        
        mock_sync_reranker = Mock()
        mock_sync_reranker.score = Mock(return_value=[0.9])
        
        test_configs = [
            {
                "reranker_provider": "provider1",
                "reranker_model": "model1",
                "fallback_rerank_models": ["fallback1"]
            },
            {
                "reranker_provider": "provider2", 
                "reranker_model": "model2",
                "fallback_rerank_models": ["fallback2"]
            }
        ]
        
        with patch('core.reranker.registry.get_reranker') as mock_get_reranker:
            mock_get_reranker.return_value = mock_sync_reranker
            
            for config in test_configs:
                state = {
                    "strategy_config": config,
                    "input_query": "测试",
                    "fused_results": [{"id": "1", "content": "内容", "score": 0.8}]
                }
                
                await reranker(state)
            
            # 验证不同配置创建了不同的缓存项
            assert len(_RERANKER_CACHE) == 2

    # TC-RR015: 缓存清理功能验证 (P2)
    def test_cache_clearing_functionality_verification(self):
        """验证缓存清理功能"""
        # 手动添加缓存项
        _RERANKER_CACHE["test_key"] = (Mock(), time.time())
        assert len(_RERANKER_CACHE) > 0
        
        # 清理缓存
        clear_reranker_cache()
        
        # 验证缓存被清空
        assert len(_RERANKER_CACHE) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])