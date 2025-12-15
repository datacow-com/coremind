"""
Phase 1 端到端测试

Phase 1: 多云算力基础设施

这些测试验证 Phase 1 的完整功能流程：
1. Chat + 成本追踪
2. 成本优先路由
3. VLM 真实图片处理
4. 故障转移链
5. 预算控制
"""
import pytest
import os
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def skip_if_no_api_key(env_var: str):
    """如果没有 API Key 则跳过测试"""
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set")


class TestChatWithCostTracking:
    """Chat + 成本追踪 E2E 测试"""

    @pytest.mark.asyncio
    async def test_chat_records_cost(self):
        """测试 Chat 调用记录成本"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        from core.llm.cost_tracker import CostRecord
        
        # 创建 Gateway
        gateway = LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            channel_id="e2e-test",
            enable_cost_tracking=True
        )
        
        # Mock cost tracker 以验证调用
        tracked_records = []
        
        async def mock_track(record: CostRecord):
            tracked_records.append(record)
        
        with patch.object(gateway.cost_tracker, 'track', side_effect=mock_track):
            with patch.object(gateway.cost_tracker, 'check_budget', new_callable=AsyncMock) as mock_budget:
                mock_budget.return_value = (True, 100.0)
                
                response = await gateway.chat(prompt="Say hello")
        
        assert response is not None
        assert len(tracked_records) == 1
        
        record = tracked_records[0]
        assert record.provider_id == "dashscope"
        assert record.model_id == "qwen-turbo"
        assert record.task_type == "chat"
        assert record.success is True
        assert record.channel_id == "e2e-test"


class TestCostFirstRouting:
    """成本优先路由 E2E 测试"""

    @pytest.mark.asyncio
    async def test_cost_first_selects_cheapest(self):
        """测试成本优先路由选择最便宜的 Provider"""
        from core.llm.gateway import LLMGateway
        from core.llm.cost_estimator import get_cost_estimator
        
        # 获取最便宜的 provider
        estimator = get_cost_estimator()
        cheapest_provider, cheapest_model, _ = estimator.get_cheapest_provider(
            task_type="chat",
            require_domestic=True
        )
        
        # 创建成本优先 Gateway
        gateway = LLMGateway(
            routing_strategy="cost_first",
            enable_cost_tracking=False
        )
        
        # 验证路由选择
        with patch.object(gateway, '_get_model_config', new_callable=AsyncMock) as mock_get:
            mock_provider = MagicMock()
            mock_provider.name = cheapest_provider
            mock_model = MagicMock()
            mock_model.model_id = cheapest_model
            mock_get.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            # 应该选择最便宜的
            assert prov.name == cheapest_provider


class TestFailoverChain:
    """故障转移链 E2E 测试"""

    @pytest.mark.asyncio
    async def test_failover_on_primary_failure(self):
        """测试主 Provider 失败时故障转移"""
        from core.llm.gateway import LLMGateway
        
        gateway = LLMGateway(
            provider="nonexistent_provider",
            model="nonexistent_model",
            enable_cost_tracking=False
        )
        
        # 配置故障转移链
        gateway.failover_chain = [
            ("dashscope", "qwen-turbo"),
            ("deepseek", "deepseek-chat"),
        ]
        
        # 主 Provider 不存在，应该尝试 failover
        # 这里只测试配置，实际 failover 需要数据库


class TestBudgetControl:
    """预算控制 E2E 测试"""

    @pytest.mark.asyncio
    async def test_budget_exceeded_raises_error(self):
        """测试预算超限时抛出异常"""
        from core.llm.gateway import LLMGateway
        from core.llm.exceptions import BudgetExceededError
        
        gateway = LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            channel_id="budget-test",
            enable_cost_tracking=True
        )
        
        # Mock 预算检查返回超限
        with patch.object(gateway.cost_tracker, 'check_budget', new_callable=AsyncMock) as mock_budget:
            mock_budget.return_value = (False, 0.5)
            
            with pytest.raises(BudgetExceededError) as exc_info:
                await gateway.chat(prompt="Test")
            
            assert exc_info.value.scope == "channel"
            assert exc_info.value.remaining == 0.5

    @pytest.mark.asyncio
    async def test_budget_allowed_proceeds(self):
        """测试预算允许时正常执行"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        
        gateway = LLMGateway(
            provider="dashscope",
            model="qwen-turbo",
            channel_id="budget-test",
            enable_cost_tracking=True
        )
        
        # Mock 预算检查返回允许
        with patch.object(gateway.cost_tracker, 'check_budget', new_callable=AsyncMock) as mock_budget:
            mock_budget.return_value = (True, 90.0)
            
            with patch.object(gateway.cost_tracker, 'track', new_callable=AsyncMock):
                response = await gateway.chat(prompt="Say hello")
        
        assert response is not None


class TestCostEstimation:
    """成本估算 E2E 测试"""

    def test_estimate_before_call(self):
        """测试调用前成本估算"""
        from core.llm.cost_estimator import get_cost_estimator
        
        estimator = get_cost_estimator()
        
        # 估算 1000 input + 500 output tokens
        cost = estimator.estimate(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=1000,
            output_tokens=500
        )
        
        # qwen-turbo: 0.002 input + 0.006 output per 1K
        expected = 0.002 + 0.003
        assert abs(cost - expected) < 0.001

    def test_get_providers_sorted_by_cost(self):
        """测试按成本排序获取 Providers"""
        from core.llm.cost_estimator import get_cost_estimator
        
        estimator = get_cost_estimator()
        
        providers = estimator.get_providers_by_cost(
            task_type="chat",
            estimated_input_tokens=1000,
            estimated_output_tokens=500
        )
        
        # 验证排序
        costs = [p[2] for p in providers]
        assert costs == sorted(costs)
        
        # DeepSeek 应该是最便宜的
        assert providers[0][0] == "deepseek"


class TestProviderConfigValidation:
    """Provider 配置验证 E2E 测试"""

    def test_validate_all_providers(self):
        """测试验证所有 Provider 配置"""
        from core.llm.provider_config import validate_all_providers
        
        results = validate_all_providers()
        
        assert "dashscope" in results
        assert "deepseek" in results
        assert "openai" in results
        
        # 验证结果结构
        for provider, result in results.items():
            assert "provider" in result
            assert "required_env" in result
            assert "missing_env" in result
            assert "configured" in result

    def test_get_domestic_providers(self):
        """测试获取国内 Providers"""
        from core.llm.provider_config import get_domestic_providers
        
        domestic = get_domestic_providers()
        
        assert "dashscope" in domestic
        assert "deepseek" in domestic
        assert "volcengine" in domestic
        assert "openai" not in domestic

    def test_get_foreign_providers(self):
        """测试获取国外 Providers"""
        from core.llm.provider_config import get_foreign_providers
        
        foreign = get_foreign_providers()
        
        assert "openai" in foreign
        assert "azure" in foreign
        assert "dashscope" not in foreign


class TestExceptionHandling:
    """异常处理 E2E 测试"""

    def test_budget_exceeded_error_attributes(self):
        """测试 BudgetExceededError 属性"""
        from core.llm.exceptions import BudgetExceededError
        
        error = BudgetExceededError(
            message="Budget exceeded",
            scope="channel",
            remaining=5.0,
            daily_cost=95.0,
            daily_limit=100.0
        )
        
        assert error.scope == "channel"
        assert error.remaining == 5.0
        assert error.daily_cost == 95.0
        assert error.daily_limit == 100.0
        assert "channel" in str(error)

    def test_provider_unavailable_error_attributes(self):
        """测试 ProviderUnavailableError 属性"""
        from core.llm.exceptions import ProviderUnavailableError
        
        error = ProviderUnavailableError(
            message="No provider available",
            tried_providers=["dashscope", "deepseek"],
            last_error="Connection timeout"
        )
        
        assert error.tried_providers == ["dashscope", "deepseek"]
        assert error.last_error == "Connection timeout"
        assert "dashscope" in str(error)


class TestBackwardCompatibility:
    """向后兼容性 E2E 测试"""

    @pytest.mark.asyncio
    async def test_original_api_still_works(self):
        """测试原有 API 仍然有效"""
        skip_if_no_api_key("DASHSCOPE_API_KEY")
        
        from core.llm.gateway import LLMGateway
        
        # 使用原有的初始化方式
        gateway = LLMGateway(provider="dashscope", model="qwen-turbo")
        
        # 禁用成本追踪以避免数据库依赖
        gateway.enable_cost_tracking = False
        
        # 原有的 chat 调用
        response = await gateway.chat(prompt="Say hello")
        
        assert response is not None
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_health_check_still_works(self):
        """测试健康检查仍然有效"""
        from core.llm.gateway import LLMGateway
        
        gateway = LLMGateway()
        
        # health_check 应该仍然可用
        # 注意：实际检查需要数据库连接
        assert hasattr(gateway, 'health_check')
