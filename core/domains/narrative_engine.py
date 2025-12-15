"""
Narrative Engine - 叙事引擎

Phase 2: 垂直领域增强
将结构化数据转换为连贯的叙事文本。
"""
from typing import Literal
import logging
import json

logger = logging.getLogger(__name__)

DetailLevel = Literal["brief", "detailed", "comprehensive"]


class NarrativeEngine:
    """叙事引擎"""

    def __init__(self, gateway=None):
        """
        初始化叙事引擎
        
        Args:
            gateway: LLMGateway 实例（可选，用于 LLM 增强生成）
        """
        self._gateway = gateway
        self._templates: dict[str, dict[str, str]] = {}  # domain_id -> {detail_level -> template}

    @property
    def gateway(self):
        """延迟加载 LLMGateway"""
        if self._gateway is None:
            try:
                from core.llm.gateway import LLMGateway
                self._gateway = LLMGateway(
                    enable_cost_tracking=True,
                    routing_strategy="cost_first"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize LLMGateway: {e}")
                self._gateway = None
        return self._gateway

    def register_template(
        self,
        domain_id: str,
        template: str,
        detail_level: DetailLevel = "detailed"
    ) -> None:
        """
        注册领域叙事模板
        
        Args:
            domain_id: 领域 ID
            template: 模板字符串，支持 {key} 占位符
            detail_level: 详细程度
        """
        if domain_id not in self._templates:
            self._templates[domain_id] = {}
        self._templates[domain_id][detail_level] = template
        logger.debug(f"Registered template for {domain_id}/{detail_level}")

    async def generate(
        self,
        structured_data: dict,
        domain_id: str,
        detail_level: DetailLevel = "detailed",
        use_llm: bool = True
    ) -> str:
        """
        生成叙事文本
        
        Args:
            structured_data: 结构化数据
            domain_id: 领域 ID
            detail_level: 详细程度 (brief, detailed, comprehensive)
            use_llm: 是否使用 LLM 增强
            
        Returns:
            str: 叙事文本
        """
        # 尝试 LLM 增强生成
        if use_llm and self.gateway:
            try:
                return await self._llm_generate(structured_data, domain_id, detail_level)
            except Exception as e:
                logger.warning(f"LLM generation failed, falling back to template: {e}")

        # 模板回退
        return self._template_fallback(structured_data, domain_id, detail_level)

    async def _llm_generate(
        self,
        structured_data: dict,
        domain_id: str,
        detail_level: DetailLevel
    ) -> str:
        """使用 LLM 生成叙事"""
        # 构建提示词
        detail_instructions = {
            "brief": "请用1-2句话简要概括。",
            "detailed": "请用3-5段详细描述，包含关键细节。",
            "comprehensive": "请进行全面深入的分析，包含所有细节和背景信息。"
        }

        prompt = f"""你是一个专业的{domain_id}领域分析师。
请根据以下结构化数据生成专业的叙事文本。

{detail_instructions.get(detail_level, detail_instructions["detailed"])}

结构化数据：
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

请直接输出叙事文本，不要包含任何解释或前缀。"""

        result = await self.gateway.chat(prompt)
        return result.strip()

    def _template_fallback(
        self,
        structured_data: dict,
        domain_id: str,
        detail_level: DetailLevel = "detailed"
    ) -> str:
        """
        模板回退生成
        
        当 LLM 不可用时使用模板生成叙事。
        """
        # 查找模板
        domain_templates = self._templates.get(domain_id, {})
        template = domain_templates.get(detail_level)

        if template:
            # 使用模板
            try:
                return self._render_template(template, structured_data)
            except Exception as e:
                logger.warning(f"Template rendering failed: {e}")

        # 默认生成
        return self._default_narrative(structured_data, domain_id, detail_level)

    def _render_template(self, template: str, data: dict) -> str:
        """渲染模板"""
        # 扁平化数据
        flat_data = self._flatten_dict(data)
        
        # 替换占位符
        result = template
        for key, value in flat_data.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        
        return result

    def _flatten_dict(self, d: dict, parent_key: str = "", sep: str = ".") -> dict:
        """扁平化嵌套字典"""
        items: list[tuple[str, any]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                items.append((new_key, ", ".join(str(x) for x in v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _default_narrative(
        self,
        structured_data: dict,
        domain_id: str,
        detail_level: DetailLevel
    ) -> str:
        """默认叙事生成"""
        lines: list[str] = []
        
        # 标题
        lines.append(f"【{domain_id.upper()} 分析报告】")
        lines.append("")

        # 根据详细程度决定输出内容
        if detail_level == "brief":
            # 简要：只输出顶层键
            for key, value in structured_data.items():
                if isinstance(value, dict):
                    lines.append(f"- {key}: {len(value)} 项")
                elif isinstance(value, list):
                    lines.append(f"- {key}: {len(value)} 条")
                else:
                    lines.append(f"- {key}: {value}")
        else:
            # 详细/全面：递归输出
            self._format_data(structured_data, lines, depth=0, max_depth=2 if detail_level == "detailed" else 10)

        return "\n".join(lines)

    def _format_data(
        self,
        data: dict | list,
        lines: list[str],
        depth: int = 0,
        max_depth: int = 2
    ) -> None:
        """递归格式化数据"""
        indent = "  " * depth

        if isinstance(data, dict):
            for key, value in data.items():
                if depth >= max_depth:
                    lines.append(f"{indent}- {key}: ...")
                elif isinstance(value, (dict, list)):
                    lines.append(f"{indent}【{key}】")
                    self._format_data(value, lines, depth + 1, max_depth)
                else:
                    lines.append(f"{indent}- {key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data[:10]):  # 最多显示 10 项
                if isinstance(item, dict):
                    lines.append(f"{indent}[{i + 1}]")
                    self._format_data(item, lines, depth + 1, max_depth)
                else:
                    lines.append(f"{indent}- {item}")
            if len(data) > 10:
                lines.append(f"{indent}... 还有 {len(data) - 10} 项")
        else:
            lines.append(f"{indent}{data}")
