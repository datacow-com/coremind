"""
CostTracker 单元测试

Phase 1: 多云算力基础设施
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.llm.cost_tracker import CostTracker, CostRecord, get_cost_tracker


class TestCostRecord:
    """CostRecord 数据类测试"""

    def test_create_cost_record_with_required_fields(self):
        """测试创建 CostRecord 必填字段"""
        record = CostRecord(
            provider_id="dashscope",
            model_id="qwen-turbo",
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0003,
            latency_ms=200,
            success=True
        )
        
        assert record.provider_id == "dashscope"
        assert record.model_id == "qwen-turbo"
        assert record.task_type == "chat"
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cost_usd == 0.0003
        assert record.latency_ms == 200
        assert record.success is True
        assert record.request_id is not None  # 自动生成
        assert record.image_count == 0
        assert record.cached is False
        assert record.error_message is None
        assert record.channel_id is None
        assert record.user_id is None

    def test_create_cost_record_with_all_fields(self):
        """测试创建 CostRecord 所有字段"""
        record = CostRecord(
            request_id="test-req-001",
            provider_id="openai",
            model_id="gpt-4o",
            task_type="vision",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.015,
            latency_ms=1500,
            success=False,
            image_count=2,
            cached=True,
            error_message="Rate limit exceeded",
            channel_id="channel-123",
            user_id="user-456"
        )
        
        assert record.request_id == "test-req-001"
        assert record.image_count == 2
        assert record.cached is True
        assert record.error_message == "Rate limit exceeded"
        assert record.channel_id == "channel-123"
        assert record.user_id == "user-456"


class TestCostTracker:
    """CostTracker 单元测试"""

    @pytest.fixture
    def mock_session(self):
        """创建 mock session"""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_session_factory(self, mock_session):
        """创建 mock session factory"""
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        factory = MagicMock(return_value=mock_context)
        return factory

    @pytest.mark.asyncio
    async def test_track_creates_record(self, mock_session, mock_session_factory):
        """测试 track() 创建记录"""
        record = CostRecord(
            provider_id="dashscope",
            model_id="qwen-turbo",
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0003,
            latency_ms=200,
            success=True
        )

        tracker = CostTracker()
        tracker._session_factory = mock_session_factory
        
        await tracker.track(record)
        
        # 验证 execute 被调用
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_daily_cost_returns_float(self, mock_session, mock_session_factory):
        """测试 get_daily_cost() 返回浮点数"""
        # Mock 返回结果
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1.5,)
        mock_session.execute.return_value = mock_result

        tracker = CostTracker()
        tracker._session_factory = mock_session_factory
        
        cost = await tracker.get_daily_cost()
        
        assert isinstance(cost, float)
        assert cost == 1.5

    @pytest.mark.asyncio
    async def test_get_daily_cost_with_channel_id(self, mock_session, mock_session_factory):
        """测试 get_daily_cost() 带 channel_id"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0.75,)
        mock_session.execute.return_value = mock_result

        tracker = CostTracker()
        tracker._session_factory = mock_session_factory
        
        cost = await tracker.get_daily_cost(channel_id="test-channel")
        
        assert cost == 0.75

    @pytest.mark.asyncio
    async def test_get_daily_cost_returns_zero_on_empty(self, mock_session, mock_session_factory):
        """测试 get_daily_cost() 无数据时返回 0"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        tracker = CostTracker()
        tracker._session_factory = mock_session_factory
        
        cost = await tracker.get_daily_cost()
        
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_check_budget_allows_under_limit(self, mock_session):
        """测试预算未超时允许"""
        # Mock budget config
        mock_budget_result = MagicMock()
        mock_budget_result.fetchone.return_value = (100.0, 0.95)  # daily_limit, hard_stop
        
        # Mock daily cost
        mock_cost_result = MagicMock()
        mock_cost_result.fetchone.return_value = (10.0,)  # 10% used
        
        mock_session.execute.side_effect = [mock_budget_result, mock_cost_result]

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        tracker = CostTracker()
        tracker._session_factory = MagicMock(return_value=mock_context)
        
        allowed, remaining = await tracker.check_budget()
        
        assert allowed is True
        assert remaining == 90.0

    @pytest.mark.asyncio
    async def test_check_budget_denies_over_limit(self, mock_session):
        """测试预算超限时拒绝"""
        # Mock budget config
        mock_budget_result = MagicMock()
        mock_budget_result.fetchone.return_value = (100.0, 0.95)  # daily_limit, hard_stop
        
        # Mock daily cost - 96% used (over 95% hard stop)
        mock_cost_result = MagicMock()
        mock_cost_result.fetchone.return_value = (96.0,)
        
        mock_session.execute.side_effect = [mock_budget_result, mock_cost_result]

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        tracker = CostTracker()
        tracker._session_factory = MagicMock(return_value=mock_context)
        
        allowed, remaining = await tracker.check_budget()
        
        assert allowed is False
        assert remaining == 4.0

    @pytest.mark.asyncio
    async def test_check_budget_allows_without_config(self, mock_session):
        """测试无预算配置时允许"""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # 无配置
        mock_session.execute.return_value = mock_result

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        
        tracker = CostTracker()
        tracker._session_factory = MagicMock(return_value=mock_context)
        
        allowed, remaining = await tracker.check_budget()
        
        assert allowed is True
        assert remaining == 100.0


class TestGetCostTracker:
    """get_cost_tracker 单例测试"""

    def test_returns_same_instance(self):
        """测试返回相同实例"""
        tracker1 = get_cost_tracker()
        tracker2 = get_cost_tracker()
        assert tracker1 is tracker2

    def test_returns_cost_tracker_instance(self):
        """测试返回 CostTracker 实例"""
        tracker = get_cost_tracker()
        assert isinstance(tracker, CostTracker)
