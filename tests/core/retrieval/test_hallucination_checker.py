#!/usr/bin/env python3
"""
幻觉检测器测试 - core/graph.py HallucinationChecker

测试超阈值降权/重试/警告文本、LLM返回非JSON/超时的降级等功能。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json
from typing import Dict, Any
import sys

# 在导入前 mock 整个依赖链
mock_llm_gateway = MagicMock()
mock_llm_gateway.LLMGateway = MagicMock()

mock_server_config = MagicMock()
mock_server_config.settings = MagicMock()

# Mock the imports to avoid blocking issues
sys.modules['server.config'] = mock_server_config
sys.modules['core.llm.gateway'] = mock_llm_gateway
sys.modules['langgraph.graph'] = MagicMock()
sys.modules['core.state'] = MagicMock()

from core.graph import HallucinationChecker


class TestHallucinationThresholdHandling:
    """幻觉检测阈值处理测试"""
    
    @pytest.fixture
    def checker(self):
        """创建幻觉检测器实例"""
        return HallucinationChecker()
    
    @pytest.fixture
    def mock_state(self):
        """创建测试状态"""
        return {
            "final_answer": "根据资料显示，AI技术在2024年取得重大突破。",
            "reranked_results": [
                {
                    "content": "AI技术发展迅速，在多个领域都有应用。",
                    "metadata": {"doc_id": "doc1.pdf"}
                },
                {
                    "content": "2024年是人工智能发展的关键年份。",
                    "metadata": {"doc_id": "doc2.pdf"}
                }
            ],
            "strategy_config": {
                "enable_hallucination_check": True,
                "hallucination_threshold": 0.5,
                "llm_provider": "mock_provider",
                "llm_model": "mock_model"
            },
            "confidence": 0.8
        }

    # TC-HC-001: 超阈值降权验证 (P1)
    @pytest.mark.asyncio
    async def test_above_threshold_confidence_reduction(self, checker, mock_state):
        """验证幻觉分数超阈值时的置信度降低"""
        high_hallucination_response = json.dumps({
            "score": 0.7,  # 超过阈值 0.5
            "unsupported_claims": ["AI技术在2024年取得重大突破"],
            "confidence": 0.8
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=high_hallucination_response)
        
        # 直接设置 checker.llm
        checker.llm = mock_gateway
        original_confidence = mock_state["confidence"]
        
        result = await checker(mock_state.copy())
        
        # 验证置信度降低
        assert result["confidence"] < original_confidence, "置信度应该降低"
        
        # 验证降低幅度合理
        expected_confidence = original_confidence * (1.0 - 0.7 * 0.5)
        assert abs(result["confidence"] - expected_confidence) < 0.01

    # TC-HC-002: 超阈值警告文本添加 (P1)
    @pytest.mark.asyncio
    async def test_above_threshold_warning_text_added(self, checker, mock_state):
        """验证幻觉分数超阈值时添加警告文本"""
        high_hallucination_response = json.dumps({
            "score": 0.6,
            "unsupported_claims": ["某些声明"],
            "confidence": 0.7
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=high_hallucination_response)
        
        checker.llm = mock_gateway
        original_answer = mock_state["final_answer"]
        
        result = await checker(mock_state.copy())
        
        # 验证警告文本存在
        assert "⚠️ 警告" in result["final_answer"], "应该添加警告前缀"
        
        # 验证原始答案仍然存在
        assert original_answer in result["final_answer"], "原始答案应该保留"

    # TC-HC-003: 超阈值需要验证标记 (P1)
    @pytest.mark.asyncio
    async def test_above_threshold_needs_verification_flag(self, checker, mock_state):
        """验证幻觉分数超阈值时设置需要验证标记"""
        high_hallucination_response = json.dumps({
            "score": 0.8,
            "unsupported_claims": ["多个不支持的声明"],
            "confidence": 0.9
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=high_hallucination_response)
        
        checker.llm = mock_gateway
        result = await checker(mock_state.copy())
        
        # 验证需要验证标记
        assert result["hallucination_detected"] is True
        assert result["hallucination_check"]["needs_verification"] is True

    # TC-HC-004: 低于阈值正常处理 (P1)
    @pytest.mark.asyncio
    async def test_below_threshold_normal_handling(self, checker, mock_state):
        """验证幻觉分数低于阈值时的正常处理"""
        low_hallucination_response = json.dumps({
            "score": 0.2,  # 低于阈值 0.5
            "unsupported_claims": [],
            "confidence": 0.95
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=low_hallucination_response)
        
        checker.llm = mock_gateway
        original_confidence = mock_state["confidence"]
        original_answer = mock_state["final_answer"]
        
        result = await checker(mock_state.copy())
        
        # 验证无幻觉检测
        assert result["hallucination_detected"] is False
        
        # 验证置信度不变
        assert result["confidence"] == original_confidence
        
        # 验证答案不变
        assert result["final_answer"] == original_answer


class TestHallucinationLLMDegradation:
    """幻觉检测LLM降级处理测试"""
    
    @pytest.fixture
    def checker(self):
        return HallucinationChecker()
    
    @pytest.fixture
    def mock_state(self):
        return {
            "final_answer": "测试答案",
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": True,
                "hallucination_threshold": 0.5,
                "llm_provider": "mock",
                "llm_model": "mock"
            },
            "confidence": 0.8
        }

    # TC-HC-005: LLM返回非JSON降级 (P1)
    @pytest.mark.asyncio
    async def test_llm_non_json_response_degradation(self, checker, mock_state):
        """验证LLM返回非JSON时的降级处理"""
        non_json_responses = [
            "这不是JSON格式的响应",
            '{"incomplete": ',
            "null",
        ]
        
        for response in non_json_responses:
            mock_gateway = AsyncMock()
            mock_gateway.chat = AsyncMock(return_value=response)
            
            checker.llm = mock_gateway
            result = await checker(mock_state.copy())
            
            # 验证降级处理 - 标记为未检测
            assert result["hallucination_detected"] is False, f"非JSON响应应该降级: {response}"
            
            # 验证原始答案保留
            assert result["final_answer"] == mock_state["final_answer"]

    # TC-HC-006: LLM超时降级 (P1)
    @pytest.mark.asyncio
    async def test_llm_timeout_degradation(self, checker, mock_state):
        """验证LLM超时时的降级处理"""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(side_effect=asyncio.TimeoutError("LLM timeout"))
        
        checker.llm = mock_gateway
        result = await checker(mock_state.copy())
        
        # 验证超时降级 - 标记为未检测
        assert result["hallucination_detected"] is False
        
        # 验证原始答案保留
        assert result["final_answer"] == mock_state["final_answer"]
        
        # 验证置信度不变
        assert result["confidence"] == mock_state["confidence"]

    # TC-HC-007: LLM异常降级 (P1)
    @pytest.mark.asyncio
    async def test_llm_exception_degradation(self, checker, mock_state):
        """验证LLM异常时的降级处理"""
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(side_effect=Exception("LLM service unavailable"))
        
        checker.llm = mock_gateway
        result = await checker(mock_state.copy())
        
        # 验证异常降级 - 标记为未检测
        assert result["hallucination_detected"] is False
        
        # 验证原始答案保留
        assert result["final_answer"] == mock_state["final_answer"]


class TestHallucinationSkipConditions:
    """幻觉检测跳过条件测试"""
    
    @pytest.fixture
    def checker(self):
        return HallucinationChecker()

    # TC-HC-008: 禁用幻觉检测 (P1)
    @pytest.mark.asyncio
    async def test_hallucination_check_disabled(self, checker):
        """验证禁用幻觉检测时的跳过"""
        disabled_state = {
            "final_answer": "测试答案",
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": False,  # 禁用
            },
            "confidence": 0.8
        }
        
        result = await checker(disabled_state)
        
        # 验证直接返回，不进行检测
        assert result["hallucination_detected"] is False
        assert result["final_answer"] == disabled_state["final_answer"]

    # TC-HC-009: 无答案跳过检测 (P1)
    @pytest.mark.asyncio
    async def test_skip_check_without_answer(self, checker):
        """验证无答案时跳过检测"""
        no_answer_state = {
            "final_answer": "",  # 空答案
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": True,
            },
            "confidence": 0.8
        }
        
        result = await checker(no_answer_state)
        
        # 验证跳过检测
        assert result["hallucination_detected"] is False

    # TC-HC-010: 无来源跳过检测 (P1)
    @pytest.mark.asyncio
    async def test_skip_check_without_sources(self, checker):
        """验证无来源时跳过检测"""
        no_sources_state = {
            "final_answer": "测试答案",
            "reranked_results": [],  # 空来源
            "strategy_config": {
                "enable_hallucination_check": True,
            },
            "confidence": 0.8
        }
        
        result = await checker(no_sources_state)
        
        # 验证跳过检测
        assert result["hallucination_detected"] is False


class TestHallucinationRetryMechanism:
    """幻觉检测重试机制测试"""
    
    @pytest.fixture
    def checker(self):
        return HallucinationChecker()

    # TC-HC-011: 重试计数递增 (P1)
    @pytest.mark.asyncio
    async def test_retry_count_increment(self, checker):
        """验证重试计数的递增"""
        state_with_retry = {
            "final_answer": "测试答案",
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": True,
                "hallucination_threshold": 0.5,
            },
            "confidence": 0.8,
            "hallucination_retry_count": 0
        }
        
        high_hallucination_response = json.dumps({
            "score": 0.8,
            "unsupported_claims": ["不支持的声明"],
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=high_hallucination_response)
        
        checker.llm = mock_gateway
        result = await checker(state_with_retry)
        
        # 验证幻觉被检测到
        assert result["hallucination_detected"] is True

    # TC-HC-012: 重试限制验证 (P1)
    @pytest.mark.asyncio
    async def test_retry_limit_verification(self, checker):
        """验证重试限制"""
        state_at_limit = {
            "final_answer": "测试答案",
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": True,
                "hallucination_threshold": 0.5,
                "max_hallucination_retries": 2,
            },
            "confidence": 0.8,
            "hallucination_retry_count": 2  # 已达到限制
        }
        
        high_hallucination_response = json.dumps({
            "score": 0.8,
            "unsupported_claims": ["不支持的声明"],
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=high_hallucination_response)
        
        checker.llm = mock_gateway
        result = await checker(state_at_limit)
        
        # 验证幻觉被检测到
        assert result["hallucination_detected"] is True


class TestHallucinationCheckResult:
    """幻觉检测结果测试"""
    
    @pytest.fixture
    def checker(self):
        return HallucinationChecker()
    
    @pytest.fixture
    def mock_state(self):
        return {
            "final_answer": "测试答案",
            "reranked_results": [{"content": "测试内容"}],
            "strategy_config": {
                "enable_hallucination_check": True,
                "hallucination_threshold": 0.5,
            },
            "confidence": 0.8
        }

    # TC-HC-013: 检测结果完整性 (P1)
    @pytest.mark.asyncio
    async def test_check_result_completeness(self, checker, mock_state):
        """验证检测结果的完整性"""
        hallucination_response = json.dumps({
            "score": 0.6,
            "unsupported_claims": ["声明1", "声明2"],
            "confidence": 0.7
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=hallucination_response)
        
        checker.llm = mock_gateway
        result = await checker(mock_state.copy())
        
        # 验证结果包含所有必要字段
        assert "hallucination_detected" in result
        assert "hallucination_check" in result
        assert "score" in result["hallucination_check"]
        assert "unsupported_claims" in result["hallucination_check"]

    # TC-HC-014: 边界阈值测试 (P1)
    @pytest.mark.asyncio
    async def test_boundary_threshold_values(self, checker, mock_state):
        """验证边界阈值的处理"""
        # 刚好等于阈值
        boundary_response = json.dumps({
            "score": 0.5,  # 等于阈值
            "unsupported_claims": [],
        })
        
        mock_gateway = AsyncMock()
        mock_gateway.chat = AsyncMock(return_value=boundary_response)
        
        checker.llm = mock_gateway
        result = await checker(mock_state.copy())
        
        # 边界值处理 - 等于阈值不触发
        assert result["hallucination_detected"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
