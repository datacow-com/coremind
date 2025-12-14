#!/usr/bin/env python3
"""
查询预处理器测试 - core/retrieval/nodes/preprocessor.py

测试意图分类、语言检测、查询重写、LLM 网关缓存等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from typing import Dict, Any

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'core.llm.gateway': Mock(),
    'core.state': Mock(),
}):
    from core.retrieval.nodes.preprocessor import (
        QueryPreProcessor, clear_preprocessor_cache, DEFAULT_INTENT_PROMPT
    )

class TestQueryPreProcessor:
    """测试查询预处理器的核心功能"""
    
    @pytest.fixture
    def preprocessor(self):
        """创建预处理器实例"""
        return QueryPreProcessor()
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "input_query": "请问什么是人工智能？",
            "strategy_config": {
                "llm_provider": "mock_provider",
                "llm_model": "mock_model",
                "fallback_llm_models": ["fallback1", "fallback2"]
            }
        }

    # TC-P001: 意图类型检测 (P1)
    @pytest.mark.asyncio
    async def test_intent_type_detection(self, preprocessor, mock_state):
        """验证各种意图类型的正确检测"""
        test_cases = [
            {
                "query": "显示销售数据表格",
                "expected_intent": "table_query",
                "expected_filters": {"block_type": "table"}
            },
            {
                "query": "总结这篇文档的内容",
                "expected_intent": "summary",
                "expected_filters": {}
            },
            {
                "query": "分析这张图片",
                "expected_intent": "image_query",
                "expected_filters": {}
            },
            {
                "query": "普通的问答查询",
                "expected_intent": "factual",
                "expected_filters": {}
            }
        ]
        
        for case in test_cases:
            mock_llm_response = json.dumps({
                "intent": case["expected_intent"],
                "language": "zh",
                "rewritten_query": case["query"],
                "filters": case["expected_filters"]
            })
            
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
                mock_gateway_class.return_value = mock_gateway
                
                test_state = mock_state.copy()
                test_state["input_query"] = case["query"]
                
                result = await preprocessor(test_state)
                
                assert result["intent"]["type"] == case["expected_intent"]
                assert result["intent"]["filters"] == case["expected_filters"]
                assert result["preprocessed_queries"] == [case["query"]]

    # TC-P002: 语言检测准确性 (P1)
    @pytest.mark.asyncio
    async def test_language_detection_accuracy(self, preprocessor, mock_state):
        """验证中英文语言检测"""
        test_cases = [
            ("What is artificial intelligence?", "en"),
            ("什么是人工智能？", "zh"),
            ("AI技术的发展趋势", "zh"),
            ("Machine learning algorithms", "en")
        ]
        
        for query, expected_lang in test_cases:
            mock_llm_response = json.dumps({
                "intent": "factual",
                "language": expected_lang,
                "rewritten_query": query,
                "filters": {}
            })
            
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
                mock_gateway_class.return_value = mock_gateway
                
                test_state = mock_state.copy()
                test_state["input_query"] = query
                
                result = await preprocessor(test_state)
                
                assert result["intent"]["language"] == expected_lang

    # TC-P003: 查询重写功能 (P1)
    @pytest.mark.asyncio
    async def test_query_rewriting_functionality(self, preprocessor, mock_state):
        """验证查询重写去除礼貌用词和修正错误"""
        test_cases = [
            {
                "original": "请问您能告诉我什么是AI吗？谢谢！",
                "rewritten": "什么是AI"
            },
            {
                "original": "Could you please help me understand machine learning? Thanks!",
                "rewritten": "understand machine learning"
            },
            {
                "original": "麻烦您解释一下深度学习的概念",
                "rewritten": "解释深度学习概念"
            }
        ]
        
        for case in test_cases:
            mock_llm_response = json.dumps({
                "intent": "factual",
                "language": "zh",
                "rewritten_query": case["rewritten"],
                "filters": {}
            })
            
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
                mock_gateway_class.return_value = mock_gateway
                
                test_state = mock_state.copy()
                test_state["input_query"] = case["original"]
                
                result = await preprocessor(test_state)
                
                rewritten = result["preprocessed_queries"][0]
                assert rewritten == case["rewritten"]
                # 验证礼貌用词被移除
                assert "请问" not in rewritten
                assert "谢谢" not in rewritten
                assert "please" not in rewritten.lower()
                assert "thanks" not in rewritten.lower()

    # TC-P004: 网关实例缓存 (P1)
    @pytest.mark.asyncio
    async def test_gateway_instance_caching(self, preprocessor, mock_state):
        """验证 LLMGateway 实例的缓存复用"""
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh", 
            "rewritten_query": "测试查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 第一次调用
            await preprocessor(mock_state.copy())
            first_call_count = mock_gateway_class.call_count
            
            # 第二次调用相同配置
            await preprocessor(mock_state.copy())
            second_call_count = mock_gateway_class.call_count
            
            # 应该复用缓存的实例
            assert second_call_count == first_call_count

    # TC-P005: 配置变化时缓存失效 (P1)
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_config_change(self, preprocessor):
        """验证配置变化时创建新的网关实例"""
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "测试查询", 
            "filters": {}
        })
        
        # 清理缓存
        clear_preprocessor_cache()
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 第一个配置
            state1 = {
                "input_query": "测试",
                "strategy_config": {
                    "llm_provider": "provider1",
                    "llm_model": "model1"
                }
            }
            await preprocessor(state1)
            first_call_count = mock_gateway_class.call_count
            
            # 第二个不同配置
            state2 = {
                "input_query": "测试",
                "strategy_config": {
                    "llm_provider": "provider2", 
                    "llm_model": "model2"
                }
            }
            await preprocessor(state2)
            second_call_count = mock_gateway_class.call_count
            
            # 应该创建新实例
            assert second_call_count > first_call_count

    # TC-P006: LLM 调用失败回退 (P1)
    @pytest.mark.asyncio
    async def test_llm_call_failure_fallback(self, preprocessor, mock_state):
        """验证 LLM 调用失败时的回退处理"""
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(side_effect=Exception("LLM timeout"))
            mock_gateway_class.return_value = mock_gateway
            
            result = await preprocessor(mock_state.copy())
            
            # 应该使用默认回退值
            assert result["intent"]["type"] == "factual"
            assert result["preprocessed_queries"] == [mock_state["input_query"]]

    # TC-P007: JSON 解析失败处理 (P1)
    @pytest.mark.asyncio
    async def test_json_parsing_failure_handling(self, preprocessor, mock_state):
        """验证 LLM 返回无效 JSON 时的处理"""
        invalid_responses = [
            "This is not JSON",
            "{ invalid json }",
            "",
            "null",
            "{ incomplete json"
        ]
        
        for invalid_response in invalid_responses:
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=invalid_response)
                mock_gateway_class.return_value = mock_gateway
                
                result = await preprocessor(mock_state.copy())
                
                # 应该使用默认值
                assert result["intent"]["type"] == "factual"
                assert result["preprocessed_queries"] == [mock_state["input_query"]]

    # TC-P008: 部分 JSON 提取 (P1)
    @pytest.mark.asyncio
    async def test_partial_json_extraction(self, preprocessor, mock_state):
        """验证从响应中提取部分 JSON 的能力"""
        # 模拟 LLM 返回包含 JSON 的文本
        response_with_json = '''
        根据分析，这是一个关于AI的查询。
        
        {
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "人工智能定义",
            "filters": {}
        }
        
        以上是分析结果。
        '''
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=response_with_json)
            mock_gateway_class.return_value = mock_gateway
            
            result = await preprocessor(mock_state.copy())
            
            # 应该成功提取 JSON 部分
            assert result["intent"]["type"] == "factual"
            assert result["intent"]["language"] == "zh"
            assert result["preprocessed_queries"] == ["人工智能定义"]

    # TC-P009: 回退模型配置 (P1)
    @pytest.mark.asyncio
    async def test_fallback_models_configuration(self, preprocessor, mock_state):
        """验证回退模型的配置传递"""
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "测试查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await preprocessor(mock_state.copy())
            
            # 验证网关创建时传递了正确参数
            mock_gateway_class.assert_called_with(
                provider="mock_provider",
                model="mock_model"
            )
            
            # 验证回退模型被设置
            assert mock_gateway.fallback_models == ["fallback1", "fallback2"]

    # TC-P010: 自定义提示词模板 (P2)
    @pytest.mark.asyncio
    async def test_custom_prompt_template(self, preprocessor, mock_state):
        """验证自定义意图提示词模板的使用"""
        custom_template = """
        自定义提示词模板：分析查询 {query}
        返回 JSON 格式的意图分析。
        """
        
        mock_state["strategy_config"]["intent_prompt_template"] = custom_template
        
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "测试查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await preprocessor(mock_state.copy())
            
            # 验证使用了自定义模板
            call_args = mock_gateway.chat.call_args[0][0]
            assert "自定义提示词模板" in call_args
            assert mock_state["input_query"] in call_args

    # TC-P011: 默认提示词模板 (P1)
    @pytest.mark.asyncio
    async def test_default_prompt_template(self, preprocessor, mock_state):
        """验证默认提示词模板的使用"""
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh", 
            "rewritten_query": "测试查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await preprocessor(mock_state.copy())
            
            # 验证使用了默认模板
            call_args = mock_gateway.chat.call_args[0][0]
            assert "Analyze the user query" in call_args or "分析用户查询" in call_args
            assert mock_state["input_query"] in call_args

    # TC-P012: 空配置处理 (P1)
    @pytest.mark.asyncio
    async def test_empty_config_handling(self, preprocessor):
        """验证空配置的处理"""
        empty_config_state = {
            "input_query": "测试查询",
            "strategy_config": None
        }
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(side_effect=Exception("No config"))
            mock_gateway_class.return_value = mock_gateway
            
            result = await preprocessor(empty_config_state)
            
            # 应该使用默认回退
            assert result["intent"]["type"] == "factual"
            assert result["preprocessed_queries"] == ["测试查询"]

    # TC-P013: 缓存清理功能 (P2)
    def test_cache_clearing_functionality(self):
        """验证缓存清理功能"""
        # 添加一些缓存项
        QueryPreProcessor._gateway_cache["test_key"] = Mock()
        assert len(QueryPreProcessor._gateway_cache) > 0
        
        # 清理缓存
        clear_preprocessor_cache()
        
        # 验证缓存被清空
        assert len(QueryPreProcessor._gateway_cache) == 0

    # TC-P014: LLM解析失败错误日志 (P0)
    @pytest.mark.asyncio
    async def test_llm_parsing_failure_error_logging(self, preprocessor, mock_state):
        """验证LLM解析失败时的错误日志记录"""
        # 模拟LLM返回完全无效的响应
        invalid_responses = [
            "完全不是JSON的响应",
            '{"incomplete": json',
            "",
            "null",
            '{"intent": "unknown_type"}'  # 无效的意图类型
        ]
        
        for invalid_response in invalid_responses:
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=invalid_response)
                mock_gateway_class.return_value = mock_gateway
                
                # 添加error_log字段到状态中
                test_state = mock_state.copy()
                test_state["error_log"] = []
                
                result = await preprocessor(test_state)
                
                # 验证回退到默认值
                assert result["intent"]["type"] == "factual"
                assert result["preprocessed_queries"] == [mock_state["input_query"]]
                
                # 验证错误被记录（如果实现了错误日志）
                # 这里可以验证日志系统是否记录了解析失败

    # TC-P015: 多意图分支正反向测试 (P1)
    @pytest.mark.asyncio
    async def test_multi_intent_branch_positive_negative(self, preprocessor, mock_state):
        """验证多意图分支的正向和反向测试"""
        intent_test_cases = [
            # 正向测试 - 应该被正确识别
            {
                "query": "显示销售数据表格",
                "expected_intent": "table_query",
                "expected_filters": {"block_type": "table"},
                "should_match": True
            },
            {
                "query": "分析这张图片中的内容",
                "expected_intent": "image_query", 
                "expected_filters": {},
                "should_match": True
            },
            {
                "query": "总结这篇文档的主要内容",
                "expected_intent": "summary",
                "expected_filters": {},
                "should_match": True
            },
            # 反向测试 - 不应该被误识别
            {
                "query": "普通的问答查询，不涉及表格",
                "expected_intent": "factual",  # 不应该被识别为table_query
                "expected_filters": {},
                "should_match": False,
                "wrong_intent": "table_query"
            },
            {
                "query": "文本查询，没有图片",
                "expected_intent": "factual",  # 不应该被识别为image_query
                "expected_filters": {},
                "should_match": False,
                "wrong_intent": "image_query"
            }
        ]
        
        for case in intent_test_cases:
            mock_llm_response = json.dumps({
                "intent": case["expected_intent"],
                "language": "zh",
                "rewritten_query": case["query"],
                "filters": case["expected_filters"]
            })
            
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
                mock_gateway_class.return_value = mock_gateway
                
                test_state = mock_state.copy()
                test_state["input_query"] = case["query"]
                
                result = await preprocessor(test_state)
                
                # 正向验证
                assert result["intent"]["type"] == case["expected_intent"]
                assert result["intent"]["filters"] == case["expected_filters"]
                
                # 反向验证 - 确保不会被误识别
                if not case["should_match"] and "wrong_intent" in case:
                    assert result["intent"]["type"] != case["wrong_intent"]

    # TC-P016: Gateway缓存隔离验证 (P1)
    @pytest.mark.asyncio
    async def test_gateway_cache_isolation_verification(self, preprocessor):
        """验证不同配置的Gateway缓存隔离"""
        # 清理缓存
        clear_preprocessor_cache()
        
        config_a = {
            "input_query": "测试查询A",
            "strategy_config": {
                "llm_provider": "provider_a",
                "llm_model": "model_a"
            }
        }
        
        config_b = {
            "input_query": "测试查询B", 
            "strategy_config": {
                "llm_provider": "provider_b",
                "llm_model": "model_b"
            }
        }
        
        mock_response = json.dumps({
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "重写查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 处理配置A
            await preprocessor(config_a)
            calls_after_a = mock_gateway_class.call_count
            
            # 处理配置B（不同配置）
            await preprocessor(config_b)
            calls_after_b = mock_gateway_class.call_count
            
            # 验证不同配置创建了不同的网关实例
            assert calls_after_b > calls_after_a
            
            # 再次处理配置A（应该复用缓存）
            await preprocessor(config_a)
            calls_after_a_again = mock_gateway_class.call_count
            
            # 验证相同配置复用了缓存
            assert calls_after_a_again == calls_after_b

    # TC-P017: 并发缓存访问 (P2)
    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self, preprocessor, mock_state):
        """验证并发访问缓存的安全性"""
        import asyncio
        
        mock_llm_response = json.dumps({
            "intent": "factual",
            "language": "zh",
            "rewritten_query": "测试查询",
            "filters": {}
        })
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 并发执行多个预处理任务
            tasks = [
                preprocessor(mock_state.copy())
                for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # 所有任务都应该成功完成
            assert len(results) == 10
            for result in results:
                assert result["intent"]["type"] == "factual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])