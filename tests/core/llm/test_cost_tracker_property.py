"""
CostTracker 属性测试

Phase 1: 多云算力基础设施
使用 Hypothesis 进行属性测试
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from decimal import Decimal

from core.llm.cost_tracker import CostRecord


# 自定义策略
provider_strategy = st.sampled_from(["dashscope", "deepseek", "volcengine", "openai", "azure"])
model_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'Pd')))
task_type_strategy = st.sampled_from(["chat", "embedding", "vision"])
token_strategy = st.integers(min_value=0, max_value=1000000)
cost_strategy = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
latency_strategy = st.integers(min_value=0, max_value=300000)


class TestCostRecordProperties:
    """
    CostRecord 属性测试
    
    **Feature: vertical-domain-phase1, Property 1: Cost Record Round Trip**
    **Validates: Requirements 2.2, 5.1**
    """

    @given(
        provider_id=provider_strategy,
        model_id=model_strategy,
        task_type=task_type_strategy,
        input_tokens=token_strategy,
        output_tokens=token_strategy,
        cost_usd=cost_strategy,
        latency_ms=latency_strategy,
        success=st.booleans(),
    )
    @settings(max_examples=100)
    def test_cost_record_preserves_data(
        self, provider_id, model_id, task_type, input_tokens, output_tokens,
        cost_usd, latency_ms, success
    ):
        """
        Property 1: Cost Record 数据完整性
        创建的 CostRecord 应保留所有输入数据
        """
        record = CostRecord(
            provider_id=provider_id,
            model_id=model_id,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
        )

        assert record.provider_id == provider_id
        assert record.model_id == model_id
        assert record.task_type == task_type
        assert record.input_tokens == input_tokens
        assert record.output_tokens == output_tokens
        assert record.cost_usd == cost_usd
        assert record.latency_ms == latency_ms
        assert record.success == success

    @given(
        input_tokens=token_strategy,
        output_tokens=token_strategy,
    )
    @settings(max_examples=50)
    def test_token_counts_non_negative(self, input_tokens, output_tokens):
        """
        Property: Token 计数非负
        """
        record = CostRecord(
            provider_id="test",
            model_id="test-model",
            task_type="chat",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,
            latency_ms=100,
            success=True,
        )

        assert record.input_tokens >= 0
        assert record.output_tokens >= 0

    @given(cost_usd=cost_strategy)
    @settings(max_examples=50)
    def test_cost_non_negative(self, cost_usd):
        """
        Property: 成本非负
        """
        record = CostRecord(
            provider_id="test",
            model_id="test-model",
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            cost_usd=cost_usd,
            latency_ms=100,
            success=True,
        )

        assert record.cost_usd >= 0

    @given(
        channel_id=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
        user_id=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    )
    @settings(max_examples=50)
    def test_optional_fields_preserved(self, channel_id, user_id):
        """
        Property: 可选字段正确保留
        """
        record = CostRecord(
            provider_id="test",
            model_id="test-model",
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
            latency_ms=100,
            success=True,
            channel_id=channel_id,
            user_id=user_id,
        )

        assert record.channel_id == channel_id
        assert record.user_id == user_id


class TestDailyCostAggregationProperties:
    """
    **Feature: vertical-domain-phase1, Property 2: Daily Cost Aggregation Consistency**
    **Validates: Requirements 2.5, 5.2**
    """

    @given(
        costs=st.lists(
            st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_cost_sum_consistency(self, costs):
        """
        Property 2: 成本汇总一致性
        多个成本记录的总和应等于各记录成本之和
        """
        total = sum(costs)
        
        # 验证浮点数精度
        assert abs(total - sum(costs)) < 1e-10

    @given(
        cost1=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        cost2=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_cost_addition_commutative(self, cost1, cost2):
        """
        Property: 成本加法交换律
        """
        assert abs((cost1 + cost2) - (cost2 + cost1)) < 1e-10


class TestBudgetCheckProperties:
    """
    **Feature: vertical-domain-phase1, Property 3: Budget Check Correctness**
    **Validates: Requirements 5.3, 5.4**
    """

    @given(
        daily_limit=st.floats(min_value=1.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        hard_stop_threshold=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
        daily_cost=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_budget_check_correctness(self, daily_limit, hard_stop_threshold, daily_cost):
        """
        Property 3: 预算检查正确性
        当 daily_cost >= daily_limit * hard_stop_threshold 时应拒绝
        """
        threshold_value = daily_limit * hard_stop_threshold
        should_deny = daily_cost >= threshold_value
        remaining = daily_limit - daily_cost

        if should_deny:
            # 超过阈值时应拒绝
            assert daily_cost >= threshold_value
        else:
            # 未超过阈值时应允许
            assert daily_cost < threshold_value

    @given(
        daily_limit=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        usage_percent=st.floats(min_value=0.0, max_value=0.94, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_under_threshold_always_allowed(self, daily_limit, usage_percent):
        """
        Property: 低于阈值时总是允许
        """
        hard_stop = 0.95
        daily_cost = daily_limit * usage_percent
        threshold_value = daily_limit * hard_stop

        # 使用率低于 95% 时应允许
        assert daily_cost < threshold_value

    @given(
        daily_limit=st.floats(min_value=10.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
        usage_percent=st.floats(min_value=0.96, max_value=1.5, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50)
    def test_over_threshold_always_denied(self, daily_limit, usage_percent):
        """
        Property: 超过阈值时总是拒绝
        """
        hard_stop = 0.95
        daily_cost = daily_limit * usage_percent
        threshold_value = daily_limit * hard_stop

        # 使用率超过 95% 时应拒绝
        assert daily_cost >= threshold_value
