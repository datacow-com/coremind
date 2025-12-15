"""
成本追踪器 - 记录 API 调用成本到数据库

Phase 1: 多云算力基础设施
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """成本记录数据类"""
    provider_id: str
    model_id: str
    task_type: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    success: bool
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    image_count: int = 0
    cached: bool = False
    error_message: Optional[str] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None


class CostTracker:
    """成本追踪器"""

    def __init__(self):
        self._session_factory = None

    @property
    def session_factory(self):
        """延迟加载 session factory"""
        if self._session_factory is None:
            from server.database import AsyncSessionLocal
            self._session_factory = AsyncSessionLocal
        return self._session_factory

    async def track(self, record: CostRecord) -> None:
        """记录成本到数据库"""
        try:
            async with self.session_factory() as session:
                await session.execute(
                    text("""
                        INSERT INTO compute_cost_records (
                            request_id, channel_id, user_id,
                            provider_id, model_id, task_type,
                            input_tokens, output_tokens, image_count,
                            cost_usd, latency_ms, cached, success, error_message
                        ) VALUES (
                            :request_id, :channel_id, :user_id,
                            :provider_id, :model_id, :task_type,
                            :input_tokens, :output_tokens, :image_count,
                            :cost_usd, :latency_ms, :cached, :success, :error_message
                        )
                    """),
                    {
                        "request_id": record.request_id,
                        "channel_id": record.channel_id,
                        "user_id": record.user_id,
                        "provider_id": record.provider_id,
                        "model_id": record.model_id,
                        "task_type": record.task_type,
                        "input_tokens": record.input_tokens,
                        "output_tokens": record.output_tokens,
                        "image_count": record.image_count,
                        "cost_usd": record.cost_usd,
                        "latency_ms": record.latency_ms,
                        "cached": record.cached,
                        "success": record.success,
                        "error_message": record.error_message,
                    }
                )
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to track cost: {e}")
            # 成本追踪失败不应阻塞主流程

    async def get_daily_cost(
        self,
        date: datetime | None = None,
        channel_id: str | None = None
    ) -> float:
        """获取每日成本"""
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")

        query = """
            SELECT COALESCE(SUM(cost_usd), 0) as total
            FROM compute_cost_records
            WHERE DATE(created_at) = :date
        """
        params: dict = {"date": date_str}

        if channel_id:
            query += " AND channel_id = :channel_id"
            params["channel_id"] = channel_id

        try:
            async with self.session_factory() as session:
                result = await session.execute(text(query), params)
                row = result.fetchone()
                return float(row[0]) if row else 0.0
        except Exception as e:
            logger.warning(f"Failed to get daily cost: {e}")
            return 0.0

    async def check_budget(
        self,
        channel_id: str | None = None,
        user_id: str | None = None
    ) -> tuple[bool, float]:
        """
        检查预算是否超限
        
        Returns:
            tuple[bool, float]: (是否允许, 剩余预算)
        """
        # 确定查询范围
        if user_id:
            scope = "user"
            scope_id = user_id
        elif channel_id:
            scope = "channel"
            scope_id = channel_id
        else:
            scope = "global"
            scope_id = None

        try:
            async with self.session_factory() as session:
                # 查询预算配置
                if scope_id:
                    result = await session.execute(
                        text("""
                            SELECT daily_limit, hard_stop_threshold
                            FROM budget_configs
                            WHERE scope = :scope
                            AND scope_id = :scope_id
                            AND is_active = true
                            LIMIT 1
                        """),
                        {"scope": scope, "scope_id": scope_id}
                    )
                else:
                    result = await session.execute(
                        text("""
                            SELECT daily_limit, hard_stop_threshold
                            FROM budget_configs
                            WHERE scope = :scope
                            AND scope_id IS NULL
                            AND is_active = true
                            LIMIT 1
                        """),
                        {"scope": scope}
                    )
                config = result.fetchone()

            if not config:
                # 无预算配置，允许调用
                return True, 100.0

            daily_limit = float(config[0]) if config[0] else 100.0
            hard_stop = float(config[1]) if config[1] else 0.95

            # 获取当日成本
            daily_cost = await self.get_daily_cost(channel_id=channel_id)
            remaining = daily_limit - daily_cost

            # 检查是否超过硬停止阈值
            if daily_cost >= daily_limit * hard_stop:
                logger.warning(
                    f"Budget exceeded: scope={scope}, scope_id={scope_id}, "
                    f"daily_cost={daily_cost:.4f}, limit={daily_limit:.2f}"
                )
                return False, remaining

            # 检查是否超过告警阈值（仅记录日志）
            alert_threshold = 0.80  # 默认 80%
            if daily_cost >= daily_limit * alert_threshold:
                logger.warning(
                    f"Budget alert: scope={scope}, scope_id={scope_id}, "
                    f"daily_cost={daily_cost:.4f}, limit={daily_limit:.2f}"
                )

            return True, remaining

        except Exception as e:
            logger.warning(f"Failed to check budget: {e}")
            # 预算检查失败时允许调用（优雅降级）
            return True, 100.0

    async def get_cost_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        channel_id: str | None = None
    ) -> dict:
        """获取成本汇总"""
        end_date = end_date or datetime.now()
        start_date = start_date or end_date.replace(day=1)

        query = """
            SELECT 
                provider_id,
                model_id,
                task_type,
                COUNT(*) as request_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cost_usd) as total_cost_usd,
                AVG(latency_ms) as avg_latency_ms
            FROM compute_cost_records
            WHERE created_at >= :start_date AND created_at < :end_date
        """
        params: dict = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d")
        }

        if channel_id:
            query += " AND channel_id = :channel_id"
            params["channel_id"] = channel_id

        query += " GROUP BY provider_id, model_id, task_type"

        try:
            async with self.session_factory() as session:
                result = await session.execute(text(query), params)
                rows = result.fetchall()
                
                return {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "channel_id": channel_id,
                    "breakdown": [
                        {
                            "provider_id": row[0],
                            "model_id": row[1],
                            "task_type": row[2],
                            "request_count": row[3],
                            "total_input_tokens": row[4],
                            "total_output_tokens": row[5],
                            "total_cost_usd": float(row[6]),
                            "avg_latency_ms": float(row[7]) if row[7] else 0
                        }
                        for row in rows
                    ]
                }
        except Exception as e:
            logger.warning(f"Failed to get cost summary: {e}")
            return {"error": str(e)}


# 全局实例
_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """获取全局 CostTracker 实例"""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
