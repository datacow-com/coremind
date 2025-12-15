"""
LLMGateway 增强功能测试

Phase 1: 多云算力基础设施
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from core.llm.gateway import LLMGateway, RoutingStrategy
from core.llm.exceptions import BudgetExceededError, ProviderUnavailableError


class TestLLMGatewayInit:
    """LLMGateway 初始化测试"""

    def test_default_init(self):
        """测试默认初始化"""
        gateway = LLMGateway()
        
        assert gateway.routing_strategy == "default"
        assert gateway.channel_id is None
        assert gateway.user_id is None
        assert gateway.enable_cost_tracking is True
        assert gateway.failover_chain == []

    def test_init_with_routing_strategy(self):
        """测试带路由策略初始化"""
        gateway = LLMGateway(routing_strategy="cost_first")
        assert gateway.routing_strategy == "cost_first"

    def test_init_with_channel_id(self):
        """测试带 channel_id 初始化"""
        gateway = LLMGateway(channel_id="test-channel")
        assert gateway.channel_id == "test-channel"

    def test_init_with_user_id(self):
        """测试带 user_id 初始化"""
        gateway = LLMGateway(user_id="test-user")
        assert gateway.user_id == "test-user"

    def test_init_disable_cost_tracking(self):
        """测试禁用成本追踪"""
        gateway = LLMGateway(enable_cost_tracking=False)
        assert gateway.enable_cost_tracking is False

    def test_backward_compatible_init(self):
        """测试向后兼容的初始化"""
        # 原有的初始化方式应该仍然有效
        gateway = LLMGateway(provider="dashscope", model="qwen-turbo")
        
        assert gateway.default_provider_name == "dashscope"
        assert gateway.default_model_name == "qwen-turbo"


class TestLLMGatewayProperties:
    """LLMGateway 属性测试"""

    def test_cost_tracker_lazy_load(self):
        """测试 cost_tracker 延迟加载"""
        gateway = LLMGateway()
        
        # 初始为 None
        assert gateway._cost_tracker is None
        
        # 访问时加载
        with patch('core.llm.cost_tracker.get_cost_tracker') as mock_get:
            mock_tracker = MagicMock()
            mock_get.return_value = mock_tracker
            
            tracker = gateway.cost_tracker
            
            assert tracker is mock_tracker
            mock_get.assert_called_once()

    def test_cost_estimator_lazy_load(self):
        """测试 cost_estimator 延迟加载"""
        gateway = LLMGateway()
        
        # 初始为 None
        assert gateway._cost_estimator is None
        
        # 访问时加载
        with patch('core.llm.cost_estimator.get_cost_estimator') as mock_get:
            mock_estimator = MagicMock()
            mock_get.return_value = mock_estimator
            
            estimator = gateway.cost_estimator
            
            assert estimator is mock_estimator
            mock_get.assert_called_once()


class TestLLMGatewayBudgetCheck:
    """预算检查测试"""

    @pytest.mark.asyncio
    async def test_check_budget_allowed(self):
        """测试预算允许"""
        gateway = LLMGateway()
        
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(True, 90.0))
        gateway._cost_tracker = mock_tracker
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is True
        assert remaining == 90.0

    @pytest.mark.asyncio
    async def test_check_budget_denied(self):
        """测试预算拒绝"""
        gateway = LLMGateway(channel_id="test-channel")
        
        mock_tracker = MagicMock()
        mock_tracker.check_budget = AsyncMock(return_value=(False, 0.5))
        gateway._cost_tracker = mock_tracker
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is False
        assert remaining == 0.5

    @pytest.mark.asyncio
    async def test_check_budget_disabled(self):
        """测试禁用成本追踪时跳过预算检查"""
        gateway = LLMGateway(enable_cost_tracking=False)
        
        allowed, remaining = await gateway._check_budget()
        
        assert allowed is True
        assert remaining == 100.0


class TestLLMGatewayRouting:
    """路由策略测试"""

    @pytest.mark.asyncio
    async def test_select_provider_default(self):
        """测试默认路由策略"""
        gateway = LLMGateway(provider="dashscope", model="qwen-turbo")
        
        mock_provider = MagicMock()
        mock_model = MagicMock()
        
        with patch.object(gateway, '_get_model_config', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            assert prov is mock_provider
            assert mdl is mock_model
            mock_get.assert_called_once_with("dashscope", "qwen-turbo")

    @pytest.mark.asyncio
    async def test_select_provider_cost_first(self):
        """测试成本优先路由策略"""
        gateway = LLMGateway(routing_strategy="cost_first")
        
        mock_provider = MagicMock()
        mock_model = MagicMock()
        
        with patch.object(gateway, '_select_cheapest_provider', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            assert prov is mock_provider
            mock_select.assert_called_once_with("chat")

    @pytest.mark.asyncio
    async def test_select_provider_performance_first(self):
        """测试性能优先路由策略"""
        gateway = LLMGateway(routing_strategy="performance_first")
        
        mock_provider = MagicMock()
        mock_model = MagicMock()
        
        with patch.object(gateway, '_select_fastest_provider', new_callable=AsyncMock) as mock_select:
            mock_select.return_value = (mock_provider, mock_model)
            
            prov, mdl = await gateway._select_provider("chat")
            
            assert prov is mock_provider
            mock_select.assert_called_once_with("chat")


class TestLLMGatewayCostTracking:
    """成本追踪测试"""

    @pytest.mark.asyncio
    async def test_track_cost_success(self):
        """测试成功调用的成本追踪"""
        gateway = LLMGateway()
        
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        mock_tracker = MagicMock()
        mock_tracker.track = AsyncMock()
        gateway._cost_tracker = mock_tracker
        
        mock_estimator = MagicMock()
        mock_estimator.estimate.return_value = 0.001
        gateway._cost_estimator = mock_estimator
        
        await gateway._track_cost(
            provider=mock_provider,
            model=mock_model,
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            success=True
        )
        
        mock_tracker.track.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_cost_disabled(self):
        """测试禁用成本追踪"""
        gateway = LLMGateway(enable_cost_tracking=False)
        
        mock_provider = MagicMock()
        mock_model = MagicMock()
        
        # 不应调用 tracker
        gateway._cost_tracker = None
        await gateway._track_cost(
            provider=mock_provider,
            model=mock_model,
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            success=True
        )
        # 无异常即通过


class TestLLMGatewayFailover:
    """故障转移测试"""

    def test_failover_chain_config(self):
        """测试故障转移链配置"""
        gateway = LLMGateway()
        gateway.failover_chain = [
            ("deepseek", "deepseek-chat"),
            ("volcengine", "doubao-pro-256k"),
        ]
        
        assert len(gateway.failover_chain) == 2
        assert gateway.failover_chain[0] == ("deepseek", "deepseek-chat")


class TestLLMGatewayCalculateCost:
    """成本计算测试"""

    def test_calculate_cost(self):
        """测试成本计算"""
        gateway = LLMGateway()
        
        mock_provider = MagicMock()
        mock_provider.name = "dashscope"
        mock_model = MagicMock()
        mock_model.model_id = "qwen-turbo"
        
        mock_estimator = MagicMock()
        mock_estimator.estimate.return_value = 0.005
        gateway._cost_estimator = mock_estimator
        
        cost = gateway._calculate_cost(
            provider=mock_provider,
            model=mock_model,
            input_tokens=1000,
            output_tokens=500
        )
        
        assert cost == 0.005
        mock_estimator.estimate.assert_called_once_with(
            provider_id="dashscope",
            model_id="qwen-turbo",
            input_tokens=1000,
            output_tokens=500,
            image_count=0
        )
