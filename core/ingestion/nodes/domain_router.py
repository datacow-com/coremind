"""
Domain Router Node - 领域路由节点

Phase 2: 垂直领域增强
在 parser 之后检测文档领域，路由到相应的领域解读器。

Features:
- 领域检测和路由
- 领域解读结果存储
- 失败时回退到标准处理
"""

import logging
import time
from typing import Any

from core.state import IngestState
from core.domains.registry import get_domain_registry
from core.domains.base_interpreter import InterpretationResult
from core.domains.exceptions import DomainInterpretationError

logger = logging.getLogger(__name__)


class DomainRouterNode:
    """
    领域路由节点
    
    在 parser 之后检测文档领域，调用相应的领域解读器。
    如果领域解读失败，回退到标准处理流程。
    """

    def __init__(self):
        self._registry = None

    @property
    def registry(self):
        """延迟加载 DomainRegistry"""
        if self._registry is None:
            self._registry = get_domain_registry()
        return self._registry

    async def __call__(self, state: IngestState) -> IngestState:
        """
        处理文档，检测领域并调用解读器
        
        Args:
            state: 当前管道状态
            
        Returns:
            IngestState: 更新后的状态
        """
        t0 = time.perf_counter()
        
        # 检查是否启用领域解读
        strategy_config = state.get("strategy_config", {})
        if not strategy_config.get("enable_domain_interpretation", True):
            logger.debug("Domain interpretation disabled, skipping")
            return state

        # 构建文档数据用于领域检测
        document = self._build_document_from_state(state)
        
        # 检测领域
        domain_id = self.registry.detect_domain(document)
        
        if not domain_id:
            logger.debug(f"No domain detected for {state.get('file_path', 'unknown')}")
            return state

        logger.info(f"Detected domain: {domain_id} for {state.get('file_path', 'unknown')}")

        # 获取解读器
        interpreter = self.registry.get_interpreter(domain_id)
        if not interpreter:
            logger.warning(f"Interpreter not found for domain: {domain_id}")
            return state

        # 执行领域解读
        try:
            config = strategy_config.get("domain_config", {}).get(domain_id, {})
            result = await interpreter.interpret(document, config)
            
            # 存储解读结果到状态
            state = self._store_interpretation_result(state, result)
            
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                f"Domain interpretation completed: domain={domain_id}, "
                f"confidence={result.confidence:.2f}, latency={latency_ms}ms"
            )
            
        except DomainInterpretationError as e:
            # 领域解读失败，记录错误但继续标准处理
            logger.warning(
                f"Domain interpretation failed for {domain_id}: {e}, "
                f"falling back to standard processing"
            )
            error_log = state.get("error_log", [])
            error_log.append({
                "stage": "domain_router",
                "domain_id": domain_id,
                "error": str(e),
                "details": e.details if hasattr(e, 'details') else {},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            state["error_log"] = error_log
            
        except Exception as e:
            # 未预期的错误，记录但继续
            logger.error(
                f"Unexpected error in domain interpretation: {e}, "
                f"falling back to standard processing"
            )
            error_log = state.get("error_log", [])
            error_log.append({
                "stage": "domain_router",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            state["error_log"] = error_log

        return state

    def _build_document_from_state(self, state: IngestState) -> dict[str, Any]:
        """
        从管道状态构建文档数据
        
        Args:
            state: 管道状态
            
        Returns:
            dict: 文档数据
        """
        document = {
            "file_path": state.get("file_path", ""),
            "file_type": state.get("file_type", ""),
            "content": state.get("extracted_text", ""),
            "raw_content": state.get("raw_content"),
            "parsed_blocks": state.get("parsed_blocks", []),
            "images": state.get("images", []),
            "metadata": {
                "channel_id": state.get("channel_id", ""),
                "kb_name": state.get("kb_name", ""),
                "batch_id": state.get("batch_id", ""),
            }
        }
        
        # 检查策略配置中是否指定了领域
        strategy_config = state.get("strategy_config", {})
        if "domain" in strategy_config:
            document["domain"] = strategy_config["domain"]
        
        return document

    def _store_interpretation_result(
        self,
        state: IngestState,
        result: InterpretationResult
    ) -> IngestState:
        """
        存储解读结果到状态
        
        Args:
            state: 管道状态
            result: 解读结果
            
        Returns:
            IngestState: 更新后的状态
        """
        # 存储到 parsed_blocks 中作为特殊块
        parsed_blocks = state.get("parsed_blocks", [])
        
        # 添加结构化数据块
        interpretation_block = {
            "type": "domain_interpretation",
            "domain_id": result.domain_id,
            "content": result.narrative,
            "structured_data": result.structured_data,
            "confidence": result.confidence,
            "metadata": result.metadata,
            "raw_elements": result.raw_elements
        }
        parsed_blocks.append(interpretation_block)
        state["parsed_blocks"] = parsed_blocks
        
        # 如果有叙事文本，追加到 extracted_text
        if result.narrative:
            extracted_text = state.get("extracted_text", "") or ""
            if extracted_text:
                extracted_text += "\n\n--- Domain Interpretation ---\n\n"
            extracted_text += result.narrative
            state["extracted_text"] = extracted_text
        
        # 更新质量指标
        quality_metrics = state.get("quality_metrics", {})
        quality_metrics["domain_interpretation_confidence"] = result.confidence
        quality_metrics["domain_id"] = result.domain_id
        state["quality_metrics"] = quality_metrics
        
        return state


def route_after_domain(state: IngestState) -> str:
    """
    领域路由后的条件路由函数
    
    根据是否有领域解读结果决定下一步：
    - 有解读结果：可以跳过某些标准处理
    - 无解读结果：继续标准处理
    
    Args:
        state: 管道状态
        
    Returns:
        str: 下一个节点名称
    """
    # 检查是否有领域解读结果
    parsed_blocks = state.get("parsed_blocks", [])
    has_interpretation = any(
        block.get("type") == "domain_interpretation"
        for block in parsed_blocks
    )
    
    if has_interpretation:
        # 有领域解读，可以直接进入 chunker
        return "chunker"
    
    # 无领域解读，继续标准处理
    return "chunker"


def should_skip_domain_router(state: IngestState) -> bool:
    """
    检查是否应该跳过领域路由
    
    Args:
        state: 管道状态
        
    Returns:
        bool: 是否跳过
    """
    strategy_config = state.get("strategy_config", {})
    return not strategy_config.get("enable_domain_interpretation", True)
