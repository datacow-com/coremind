#!/usr/bin/env python3
"""
引用生成器测试 - core/retrieval/nodes/generator.py

测试引用解析、置信度计算、LLM 配置缓存、可配置提示词等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import re
from typing import Dict, Any, List

# Mock the imports to avoid blocking issues
with patch.dict('sys.modules', {
    'core.llm.gateway': Mock(),
    'core.state': Mock(),
}):
    from core.retrieval.nodes.generator import (
        CitationGenerator, clear_generator_cache, 
        DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT,
        _GENERATOR_GATEWAY_CACHE
    )

class TestCitationGenerator:
    """测试引用生成器的核心功能"""
    
    @pytest.fixture
    def generator(self):
        """创建生成器实例"""
        return CitationGenerator()
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "strategy_config": {
                "llm_provider": "mock_provider",
                "llm_model": "mock_model",
                "top_k": 5
            },
            "input_query": "什么是人工智能？",
            "reranked_results": [
                {
                    "id": "chunk_1",
                    "content": "人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
                    "metadata": {
                        "doc_id": "ai_intro.pdf",
                        "page_num": 1,
                        "bbox": [100, 200, 400, 250]
                    }
                },
                {
                    "id": "chunk_2",
                    "content": "机器学习是人工智能的一个重要子领域，专注于算法和统计模型的开发。",
                    "metadata": {
                        "doc_id": "ml_basics.pdf", 
                        "page_num": 2,
                        "bbox": [50, 150, 350, 200]
                    }
                },
                {
                    "id": "chunk_3",
                    "content": "深度学习使用多层神经网络来模拟人脑的工作方式，是机器学习的一个分支。",
                    "metadata": {
                        "doc_id": "dl_guide.pdf",
                        "page_num": 1,
                        "bbox": [80, 300, 380, 350]
                    }
                }
            ],
            "is_relevant": True,
            "retrieval_confidence": 0.8
        }

    # TC-G001: 引用标签解析 (P1)
    @pytest.mark.asyncio
    async def test_citation_tag_parsing(self, generator, mock_state):
        """验证 `<cite id="[索引]">内容</cite>` 的正确解析"""
        # Mock LLM 返回包含引用标签的答案
        mock_llm_response = '''
        人工智能是一个广泛的领域。<cite id="[0]">人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。</cite>
        
        其中一个重要的子领域是机器学习。<cite id="[1]">机器学习是人工智能的一个重要子领域，专注于算法和统计模型的开发。</cite>
        
        而深度学习则是机器学习的进一步发展。<cite id="[2]">深度学习使用多层神经网络来模拟人脑的工作方式。</cite>
        '''
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            result = await generator(mock_state.copy())
            
            # 验证引用解析
            citations = result["citations"]
            assert len(citations) == 3
            
            # 验证第一个引用
            cite1 = citations[0]
            assert cite1["doc_id"] == "ai_intro.pdf"
            assert cite1["page"] == 1
            assert cite1["bbox"] == [100, 200, 400, 250]
            assert cite1["chunk_id"] == "chunk_1"
            assert "人工智能（AI）是计算机科学的一个分支" in cite1["content"]
            
            # 验证第二个引用
            cite2 = citations[1]
            assert cite2["doc_id"] == "ml_basics.pdf"
            assert cite2["page"] == 2
            
            # 验证第三个引用
            cite3 = citations[2]
            assert cite3["doc_id"] == "dl_guide.pdf"

    # TC-G002: 无效引用索引处理 (P1)
    @pytest.mark.asyncio
    async def test_invalid_citation_index_handling(self, generator, mock_state):
        """验证超出范围的引用索引处理"""
        # Mock 答案包含超出范围的引用索引
        mock_llm_response = '''
        这是一个有效的引用：<cite id="[0]">人工智能的定义</cite>
        这是一个无效的引用：<cite id="[99]">不存在的文档内容</cite>
        这是另一个有效的引用：<cite id="[1]">机器学习的介绍</cite>
        '''
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            result = await generator(mock_state.copy())
            
            # 验证只有有效的引用被包含
            citations = result["citations"]
            assert len(citations) == 2  # 只有索引0和1有效
            
            # 验证无效引用被忽略
            doc_ids = [cite["doc_id"] for cite in citations]
            assert "ai_intro.pdf" in doc_ids
            assert "ml_basics.pdf" in doc_ids

    # TC-G003: 引用元数据提取 (P1)
    @pytest.mark.asyncio
    async def test_citation_metadata_extraction(self, generator, mock_state):
        """验证引用的完整元数据提取"""
        mock_llm_response = '<cite id="[0]">完整的引用内容</cite>'
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            result = await generator(mock_state.copy())
            
            citation = result["citations"][0]
            
            # 验证所有必需的元数据字段
            required_fields = ["doc_id", "page", "bbox", "content", "chunk_id"]
            for field in required_fields:
                assert field in citation
            
            # 验证具体值
            assert citation["doc_id"] == "ai_intro.pdf"
            assert citation["page"] == 1
            assert citation["bbox"] == [100, 200, 400, 250]
            assert citation["content"] == "完整的引用内容"
            assert citation["chunk_id"] == "chunk_1"

    # TC-G004: 多因素置信度计算 (P1)
    @pytest.mark.asyncio
    async def test_multi_factor_confidence_calculation(self, generator, mock_state):
        """验证基于检索置信度和引用覆盖率的综合置信度"""
        test_cases = [
            {
                "retrieval_confidence": 0.8,
                "citations_count": 3,  # 覆盖所有3个文档
                "total_docs": 3,
                "expected_confidence": 0.8 * 0.6 + 1.0 * 0.4  # 0.88
            },
            {
                "retrieval_confidence": 0.6,
                "citations_count": 1,  # 只覆盖1个文档
                "total_docs": 3,
                "expected_confidence": 0.6 * 0.6 + (1/3) * 0.4  # 0.493
            },
            {
                "retrieval_confidence": 0.9,
                "citations_count": 2,  # 覆盖2个文档
                "total_docs": 3,
                "expected_confidence": 0.9 * 0.6 + (2/3) * 0.4  # 0.807
            }
        ]
        
        for case in test_cases:
            # 构造对应数量的引用
            citations_text = ""
            for i in range(case["citations_count"]):
                citations_text += f'<cite id="[{i}]">引用内容{i}</cite> '
            
            mock_llm_response = f"这是答案内容。{citations_text}"
            
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
                mock_gateway_class.return_value = mock_gateway
                
                test_state = mock_state.copy()
                test_state["retrieval_confidence"] = case["retrieval_confidence"]
                
                result = await generator(test_state)
                
                # 验证置信度计算
                confidence = result["confidence"]
                expected = case["expected_confidence"]
                assert abs(confidence - expected) < 0.01, f"Expected {expected}, got {confidence}"

    # TC-G005: 诚实"不知道"答案处理 (P1)
    @pytest.mark.asyncio
    async def test_honest_dont_know_answer_handling(self, generator, mock_state):
        """验证"无法回答"类答案的置信度"""
        honest_responses = [
            "根据提供的资料无法回答这个问题。",
            "抱歉，我无法回答您的问题。",
            "提供的文档中没有相关信息。"
        ]
        
        for response in honest_responses:
            with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
                mock_gateway = AsyncMock()
                mock_gateway.chat = AsyncMock(return_value=response)
                mock_gateway_class.return_value = mock_gateway
                
                result = await generator(mock_state.copy())
                
                # 验证诚实回答的置信度
                assert "无法回答" in result["final_answer"]
                assert result["confidence"] == 0.3
                assert result["citations"] == []

    # TC-G006: 网关缓存复用 (P1)
    @pytest.mark.asyncio
    async def test_gateway_cache_reuse(self, generator, mock_state):
        """验证相同配置的 LLM 网关缓存"""
        clear_generator_cache()
        
        mock_llm_response = "测试答案"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 第一次调用
            await generator(mock_state.copy())
            first_call_count = mock_gateway_class.call_count
            
            # 第二次调用相同配置
            await generator(mock_state.copy())
            second_call_count = mock_gateway_class.call_count
            
            # 应该复用缓存的网关实例
            assert second_call_count == first_call_count

    # TC-G007: 配置变化缓存失效 (P1)
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_config_change(self, generator):
        """验证 LLM 配置变化时缓存失效"""
        clear_generator_cache()
        
        mock_llm_response = "测试答案"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            # 第一个配置
            state1 = {
                "strategy_config": {
                    "llm_provider": "provider1",
                    "llm_model": "model1"
                },
                "input_query": "测试",
                "reranked_results": [],
                "is_relevant": False
            }
            await generator(state1)
            first_call_count = mock_gateway_class.call_count
            
            # 第二个不同配置
            state2 = {
                "strategy_config": {
                    "llm_provider": "provider2",
                    "llm_model": "model2"
                },
                "input_query": "测试",
                "reranked_results": [],
                "is_relevant": False
            }
            await generator(state2)
            second_call_count = mock_gateway_class.call_count
            
            # 应该创建新的网关实例
            assert second_call_count > first_call_count

    # TC-G008: 自定义系统提示词 (P2)
    @pytest.mark.asyncio
    async def test_custom_system_prompt(self, generator, mock_state):
        """验证自定义系统提示词的使用"""
        custom_system_prompt = """
        你是一个专业的AI助手，专门回答技术问题。
        请基于提供的上下文回答问题，并标注引用来源。
        """
        
        mock_state["strategy_config"]["generation_system_prompt"] = custom_system_prompt
        
        mock_llm_response = "基于自定义提示词的回答"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await generator(mock_state.copy())
            
            # 验证使用了自定义系统提示词
            call_args = mock_gateway.chat.call_args[1]["prompt"]
            assert "专业的AI助手" in call_args
            assert "技术问题" in call_args

    # TC-G009: 自定义用户提示词模板 (P2)
    @pytest.mark.asyncio
    async def test_custom_user_prompt_template(self, generator, mock_state):
        """验证自定义用户提示词模板"""
        custom_user_template = """
        参考资料：
        {context}
        
        用户问题：{query}
        
        请提供详细的回答并标注引用。
        """
        
        mock_state["strategy_config"]["generation_user_prompt"] = custom_user_template
        
        mock_llm_response = "基于自定义模板的回答"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await generator(mock_state.copy())
            
            # 验证使用了自定义用户模板
            call_args = mock_gateway.chat.call_args[1]["prompt"]
            assert "参考资料：" in call_args
            assert "用户问题：" in call_args
            assert mock_state["input_query"] in call_args

    # TC-G010: 默认提示词模板 (P1)
    @pytest.mark.asyncio
    async def test_default_prompt_templates(self, generator, mock_state):
        """验证默认提示词模板的使用"""
        mock_llm_response = "使用默认模板的回答"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await generator(mock_state.copy())
            
            # 验证使用了默认模板
            call_args = mock_gateway.chat.call_args[1]["prompt"]
            assert "严谨的助手" in call_args or "必须基于提供的上下文" in call_args

    # TC-G011: 无相关结果处理 (P1)
    @pytest.mark.asyncio
    async def test_no_relevant_results_handling(self, generator):
        """验证无相关结果时的处理"""
        no_relevant_state = {
            "strategy_config": {
                "llm_provider": "mock_provider",
                "llm_model": "mock_model"
            },
            "input_query": "测试查询",
            "reranked_results": [],
            "is_relevant": False
        }
        
        result = await generator(no_relevant_state)
        
        # 验证无相关结果的处理
        assert "未找到相关信息" in result["final_answer"]
        assert result["citations"] == []
        assert result["confidence"] == 0.0

    # TC-G012: 空文档列表处理 (P1)
    @pytest.mark.asyncio
    async def test_empty_documents_list_handling(self, generator):
        """验证空文档列表的处理"""
        empty_docs_state = {
            "strategy_config": {
                "llm_provider": "mock_provider",
                "llm_model": "mock_model"
            },
            "input_query": "测试查询",
            "reranked_results": [],
            "is_relevant": True  # 标记为相关但无文档
        }
        
        result = await generator(empty_docs_state)
        
        # 验证空文档的处理
        assert "未找到相关信息" in result["final_answer"]
        assert result["citations"] == []
        assert result["confidence"] == 0.0

    # TC-G013: 上下文构建验证 (P1)
    @pytest.mark.asyncio
    async def test_context_building_verification(self, generator, mock_state):
        """验证上下文构建的正确性"""
        mock_llm_response = "测试回答"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            await generator(mock_state.copy())
            
            # 验证上下文构建
            call_args = mock_gateway.chat.call_args[1]["prompt"]
            
            # 验证包含文档内容
            assert "人工智能（AI）是计算机科学的一个分支" in call_args
            assert "机器学习是人工智能的一个重要子领域" in call_args
            
            # 验证包含来源信息
            assert "ai_intro.pdf" in call_args
            assert "ml_basics.pdf" in call_args
            
            # 验证包含页码信息
            assert "页码: 1" in call_args or "页码: 2" in call_args

    # TC-G014: 无引用但有答案的置信度 (P1)
    @pytest.mark.asyncio
    async def test_no_citations_but_has_answer_confidence(self, generator, mock_state):
        """验证无引用但有答案时的置信度计算"""
        # 无引用标签的答案
        mock_llm_response = "人工智能是一个复杂的领域，涉及多个技术分支。"
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            result = await generator(mock_state.copy())
            
            # 验证无引用时的置信度计算
            expected_confidence = mock_state["retrieval_confidence"] * 0.5  # 0.8 * 0.5 = 0.4
            assert abs(result["confidence"] - expected_confidence) < 0.01
            assert result["citations"] == []

    # TC-G015: 缓存清理功能验证 (P2)
    def test_cache_clearing_functionality_verification(self):
        """验证缓存清理功能"""
        # 手动添加缓存项
        _GENERATOR_GATEWAY_CACHE["test_key"] = Mock()
        assert len(_GENERATOR_GATEWAY_CACHE) > 0
        
        # 清理缓存
        clear_generator_cache()
        
        # 验证缓存被清空
        assert len(_GENERATOR_GATEWAY_CACHE) == 0

    # TC-G016: 复杂引用模式解析 (P2)
    @pytest.mark.asyncio
    async def test_complex_citation_pattern_parsing(self, generator, mock_state):
        """验证复杂引用模式的解析"""
        # 包含多行、嵌套内容的引用
        mock_llm_response = '''
        人工智能的发展历程很长。<cite id="[0]">人工智能（AI）是计算机科学的一个分支，
        致力于创建能够执行通常需要人类智能的任务的系统。
        这个定义涵盖了多个方面。</cite>
        
        同时，<cite id="[1]">机器学习是人工智能的一个重要子领域，
        专注于算法和统计模型的开发。</cite>这是核心技术之一。
        '''
        
        with patch('core.llm.gateway.LLMGateway') as mock_gateway_class:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=mock_llm_response)
            mock_gateway_class.return_value = mock_gateway
            
            result = await generator(mock_state.copy())
            
            # 验证复杂引用被正确解析
            citations = result["citations"]
            assert len(citations) == 2
            
            # 验证多行内容被正确提取
            cite1_content = citations[0]["content"]
            assert "人工智能（AI）是计算机科学的一个分支" in cite1_content
            assert "这个定义涵盖了多个方面" in cite1_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])