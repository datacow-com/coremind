"""
State Factory - 简化 IngestState 创建并集成能力加载器

这个模块提供了便捷的工厂函数来创建 IngestState，自动：
1. 填充默认值
2. 根据 KB 配置加载能力
3. 验证必需字段
"""

import uuid
from typing import Any

from core.state import IngestState, StrategyConfig


async def create_ingest_state(
    *,
    file_path: str,
    kb_name: str,
    channel_id: str = "default",
    task_id: str | None = None,
    file_type: str = "pdf",
    batch_id: str | None = None,
    version: int = 1,
    strategy_config: dict[str, Any] | None = None,
    enable_capabilities: bool = True,
) -> IngestState:
    """
    创建 IngestState 的便捷工厂函数

    Args:
        file_path: 文件路径（必需）
        kb_name: 知识库名称（必需）
        channel_id: 渠道ID，用于多租户隔离
        task_id: 任务ID，默认自动生成
        file_type: 文件类型，如 pdf, docx, pptx 等
        batch_id: 批次ID，默认自动生成
        version: KB 版本号
        strategy_config: 策略配置字典
        enable_capabilities: 是否启用能力加载器

    Returns:
        完整初始化的 IngestState
    """
    # 生成默认 IDs
    _task_id = task_id or str(uuid.uuid4())
    _batch_id = batch_id or str(uuid.uuid4())

    # 构建策略配置
    if strategy_config:
        _strategy = StrategyConfig(**strategy_config).model_dump()
    else:
        _strategy = StrategyConfig().model_dump()

    # 加载能力（可选）
    capability_loader = None
    if enable_capabilities:
        try:
            from core.capabilities.loader import get_loader_for_kb
            from core.storage.kb_config import load_kb_config

            kb_config = load_kb_config(kb_name)
            capability_loader = await get_loader_for_kb(kb_name, kb_config)
        except Exception as e:
            # 能力加载失败不应阻塞摄取流程
            import logging

            logging.getLogger(__name__).warning(
                f"Failed to load capabilities for KB '{kb_name}': {e}"
            )
            capability_loader = None

    return IngestState(
        channel_id=channel_id,
        task_id=_task_id,
        file_path=file_path,
        file_type=file_type,
        batch_id=_batch_id,
        kb_name=kb_name,
        version=version,
        strategy_config=_strategy,
        capability_loader=capability_loader,
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        processing_stage="upload",
        retry_count=0,
        error_log=[],
        progress={"total_chunks": 0, "completed_chunks": 0},
        quality_metrics={},
    )


def create_ingest_state_sync(
    *,
    file_path: str,
    kb_name: str,
    channel_id: str = "default",
    task_id: str | None = None,
    file_type: str = "pdf",
    batch_id: str | None = None,
    version: int = 1,
    strategy_config: dict[str, Any] | None = None,
) -> IngestState:
    """
    同步版本的状态创建（不加载能力）

    用于不需要能力加载器的场景，如简单测试
    """
    _task_id = task_id or str(uuid.uuid4())
    _batch_id = batch_id or str(uuid.uuid4())

    if strategy_config:
        _strategy = StrategyConfig(**strategy_config).model_dump()
    else:
        _strategy = StrategyConfig().model_dump()

    return IngestState(
        channel_id=channel_id,
        task_id=_task_id,
        file_path=file_path,
        file_type=file_type,
        batch_id=_batch_id,
        kb_name=kb_name,
        version=version,
        strategy_config=_strategy,
        capability_loader=None,
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        processing_stage="upload",
        retry_count=0,
        error_log=[],
        progress={"total_chunks": 0, "completed_chunks": 0},
        quality_metrics={},
    )
