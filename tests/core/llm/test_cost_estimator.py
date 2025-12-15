"""
CostEstimator 单元测试

Phase 1: 多云算力基础设施
"""
import pytest
from core.llm.cost_estimator import CostEstimator, get_cost_estimator


class TestCostEstimator:
    """CostEstimator 单元测试"""

    @pytest.fixture
    def estimator(self):
        """创建 CostEstimator 实例"""
        return CostEstimator()

    def test_estimate_dashscope_qwen_turbo(self, estimator):
        """测试 DashScope qwen-turbo 成本估算"""
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        # qwen-turbo: input=0.002, output=0.006 per 1K
        expected = (1000 / 1000) * 0.002 + (500 / 1000) * 0.006
        assert abs(cost - expected) < 1e-6

    def test_estimate_deepseek_chat(self, estimator):
        """测试 DeepSeek chat 成本估算"""
        cost = estimator.estimate(
            provider_id="deepseek",
            model_id="deepseek-chat",
            input_tokens=10000,
            output_tokens=5000
        )
        
        # deepseek-chat: input=0.00014, output=0.00028 per 1K
        expected = (10000 / 1000) * 0.00014 + (5000 / 1000) * 0.00028
        assert abs(cost - expected) < 1e-6

    def test_estimate_with_images(self, estimator):
        """测试带图片的成本估算"""
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-vl-max",
            input_tokens=1000,
            output_tokens=500,
            image_count=2
        )
        
        # 应包含图片成本
        assert cost > 0
        
        # 比较无图片的成本
        cost_no_image = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-vl-max",
            input_tokens=1000,
            output_tokens=500,
            image_count=0
        )
        assert cost > cost_no_image

    def test_estimate_unknown_provider_uses_default(self, estimator):
        """测试未知 Provider 使用默认成本"""
        cost = estimator.estimate(
            provider_id="unknown_provider",
            model_id="unknown_model",
            input_tokens=1000,
            output_tokens=500
        )
        
        # 应使用默认成本 (0.01 input, 0.03 output)
        expected = (1000 / 1000) * 0.01 + (500 / 1000) * 0.03
        assert abs(cost - expected) < 1e-6

    def test_estimate_zero_tokens(self, estimator):
        """测试零 token 成本"""
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=0,
            output_tokens=0
        )
        
        assert cost == 0.0

    def test_get_cheapest_provider_chat(self, estimator):
        """测试获取最便宜的 chat Provider"""
        provider, model, cost = estimator.get_cheapest_provider(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        assert provider is not None
        assert model is not None
        assert cost > 0
        
        # 验证返回的是成本最低的（可能是 deepseek 或 gemini）
        # 获取所有 providers 按成本排序
        all_providers = estimator.get_providers_by_cost(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        # 返回的应该是最便宜的
        assert (provider, model, cost) == all_providers[0]

    def test_get_cheapest_provider_domestic(self, estimator):
        """测试获取最便宜的国内 Provider"""
        provider, model, cost = estimator.get_cheapest_provider(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
            require_domestic=True
        )
        
        assert provider in ["dashscope", "deepseek", "volcengine"]

    def test_get_cheapest_provider_embedding(self, estimator):
        """测试获取最便宜的 embedding Provider"""
        provider, model, cost = estimator.get_cheapest_provider(
            task_type="embedding",
            estimated_input_tokens=1000,
            estimated_output_tokens=0
        )
        
        assert "embedding" in model.lower()

    def test_get_providers_by_cost(self, estimator):
        """测试按成本排序获取 Providers"""
        providers = estimator.get_providers_by_cost(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        assert len(providers) > 0
        
        # 验证按成本升序排列
        costs = [p[2] for p in providers]
        assert costs == sorted(costs)

    def test_get_providers_by_cost_vision(self, estimator):
        """测试获取 vision Providers"""
        providers = estimator.get_providers_by_cost(
            task_type="vision",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        # 应只返回 vision 模型
        for provider, model, cost in providers:
            assert "vl" in model.lower() or "vision" in model.lower()

    def test_estimate_case_insensitive(self, estimator):
        """测试 Provider/Model 名称大小写不敏感"""
        cost1 = estimator.estimate("DashScope", "Qwen-Turbo", 1000, 500)
        cost2 = estimator.estimate("dashscope", "qwen-turbo", 1000, 500)
        
        assert abs(cost1 - cost2) < 1e-6


class TestGetCostEstimator:
    """get_cost_estimator 单例测试"""

    def test_returns_same_instance(self):
        """测试返回相同实例"""
        estimator1 = get_cost_estimator()
        estimator2 = get_cost_estimator()
        assert estimator1 is estimator2

    def test_returns_cost_estimator_instance(self):
        """测试返回 CostEstimator 实例"""
        estimator = get_cost_estimator()
        assert isinstance(estimator, CostEstimator)


class TestCostEstimatorEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def estimator(self):
        return CostEstimator()

    def test_large_token_count(self, estimator):
        """测试大量 token"""
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=1000000,
            output_tokens=500000
        )
        
        assert cost > 0
        assert cost < 10000  # 合理范围

    def test_fuzzy_model_match(self, estimator):
        """测试模糊模型匹配"""
        # qwen-turbo-latest 应匹配 qwen-turbo
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo-latest",
            input_tokens=1000,
            output_tokens=500
        )
        
        expected_cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        # 应该匹配到 qwen-turbo 的成本
        assert abs(cost - expected_cost) < 1e-6
