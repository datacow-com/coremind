"""
Comic Interpreter - 漫画解读器

Phase 2: 垂直领域增强
实现漫画的深度解读，支持分格检测、对话提取、场景描述和故事叙事构建。
"""
import logging
from pathlib import Path
from typing import Any

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError
from core.domains.comic.panel_detector import PanelDetector, DetectionResult

logger = logging.getLogger(__name__)


class ComicInterpreter(BaseDomainInterpreter):
    """
    漫画解读器
    
    支持从漫画图像中提取分格、对话、场景和角色信息，
    并构建连贯的故事叙事。
    """

    domain_id = "comic"
    requires_gpu = True
    recommended_vram_mb = 8192

    def __init__(self):
        super().__init__()
        self._ontology: OntologySchema | None = None
        self._narrative_engine = None
        self._panel_detector: PanelDetector | None = None

    @property
    def narrative_engine(self):
        """延迟加载叙事引擎"""
        if self._narrative_engine is None:
            from core.domains.narrative_engine import NarrativeEngine
            self._narrative_engine = NarrativeEngine()
            self._register_templates()
        return self._narrative_engine

    @property
    def panel_detector(self) -> PanelDetector:
        """延迟加载分格检测器"""
        if self._panel_detector is None:
            self._panel_detector = PanelDetector(reading_order="auto")
        return self._panel_detector

    def _register_templates(self) -> None:
        """注册漫画叙事模板"""
        brief_template = "这是一个{panel_count}格漫画，讲述了{story_summary}的故事。"
        
        detailed_template = """【漫画分析】
分格数量：{panel_count}
阅读顺序：{reading_order}

【故事内容】
{story_narrative}

【角色】
{characters}

【艺术风格】
{art_style}"""

        self._narrative_engine.register_template(self.domain_id, brief_template, "brief")
        self._narrative_engine.register_template(self.domain_id, detailed_template, "detailed")

    def get_ontology(self) -> OntologySchema:
        """获取漫画本体定义"""
        if self._ontology is None:
            ontology_path = Path(__file__).parent / "ontology.yaml"
            if ontology_path.exists():
                self._ontology = OntologySchema.from_yaml(str(ontology_path))
            else:
                self._ontology = self._get_default_ontology()
        return self._ontology

    def _get_default_ontology(self) -> OntologySchema:
        """获取默认本体定义"""
        return OntologySchema.from_dict({
            "domain_id": "comic",
            "version": "1.0",
            "entity_types": {
                "panel": {
                    "description": "漫画分格",
                    "fields": {
                        "index": {"type": "integer", "minimum": 0},
                        "scene_description": {"type": "string"},
                        "characters": {"type": "array", "items_type": "string"},
                        "dialogue": {"type": "array", "items_type": "string"},
                        "action": {"type": "string"},
                    },
                    "required": ["index"],
                },
                "character": {
                    "description": "角色",
                    "fields": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "appearances": {"type": "array", "items_type": "integer"},
                    },
                    "required": ["name"],
                },
                "dialogue": {
                    "description": "对话",
                    "fields": {
                        "text": {"type": "string"},
                        "speaker": {"type": "string"},
                        "panel_index": {"type": "integer"},
                        "bubble_type": {"type": "string", "enum": ["speech", "thought", "narration", "sfx"]},
                    },
                    "required": ["text", "panel_index"],
                },
                "art_style": {
                    "description": "艺术风格",
                    "fields": {
                        "style": {"type": "string"},
                        "color_scheme": {"type": "string"},
                        "line_work": {"type": "string"},
                    },
                    "required": [],
                },
            },
            "relationships": [
                {"name": "contains_dialogue", "source_type": "panel", "target_type": "dialogue", "cardinality": "many"},
                {"name": "features_character", "source_type": "panel", "target_type": "character", "cardinality": "many"},
            ],
        })

    def validate_output(self, result: InterpretationResult) -> tuple[bool, list[str]]:
        """验证解读结果是否符合本体定义"""
        ontology = self.get_ontology()
        return ontology.validate(result.structured_data)

    async def interpret(
        self,
        document: dict,
        config: dict | None = None
    ) -> InterpretationResult:
        """
        解读漫画文档
        
        Args:
            document: 文档数据，包含 images, metadata 等
            config: 解读配置
                - detail_level: brief/detailed/comprehensive
                - use_llm: 是否使用 LLM 增强
                - reading_order: ltr/rtl/auto
                - analyze_art_style: 是否分析艺术风格
                
        Returns:
            InterpretationResult: 解读结果
        """
        config = config or {}
        detail_level = config.get("detail_level", "detailed")
        use_llm = config.get("use_llm", True)
        reading_order = config.get("reading_order", "auto")
        analyze_art_style = config.get("analyze_art_style", True)

        try:
            # 获取图像数据
            images = document.get("images", [])
            if not images:
                # 尝试从 content 获取（可能是 base64 编码）
                content = document.get("content")
                if content and isinstance(content, bytes):
                    images = [content]
                elif not images:
                    raise DomainInterpretationError(
                        "No images found in document",
                        domain_id=self.domain_id,
                        stage="interpret",
                        details={"document_keys": list(document.keys())},
                    )

            # 1. 检测分格和气泡
            raw_elements: list[dict] = []
            all_panels: list[dict] = []
            all_dialogues: list[dict] = []
            
            for img_idx, img_data in enumerate(images):
                if isinstance(img_data, dict) and "data" in img_data:
                    img_bytes = img_data["data"]
                elif isinstance(img_data, bytes):
                    img_bytes = img_data
                else:
                    continue
                
                # 配置分格检测器
                self._panel_detector = PanelDetector(reading_order=reading_order)
                detection = self.panel_detector.detect(img_bytes)
                
                raw_elements.append({
                    "type": "detection",
                    "image_index": img_idx,
                    "detection": detection.to_dict(),
                })
                
                # 2. 使用 VLM 分析每个分格
                panel_analyses = await self._analyze_panels(img_bytes, detection, config)
                all_panels.extend(panel_analyses)
                
                # 3. 提取对话（OCR）
                dialogues = await self._extract_dialogues(img_bytes, detection, config)
                all_dialogues.extend(dialogues)
                
                raw_elements.append({
                    "type": "panel_analysis",
                    "image_index": img_idx,
                    "panels": panel_analyses,
                })

            # 4. 分析艺术风格
            art_style = {}
            if analyze_art_style and images:
                first_img = images[0]
                if isinstance(first_img, dict) and "data" in first_img:
                    first_img = first_img["data"]
                if isinstance(first_img, bytes):
                    art_style = await self._analyze_art_style(first_img)

            # 5. 构建结构化数据
            structured_data = self._build_structured_data(
                all_panels, all_dialogues, art_style, detection if images else None
            )

            # 6. 生成叙事文本
            narrative = await self.narrative_engine.generate(
                structured_data,
                self.domain_id,
                detail_level=detail_level,
                use_llm=use_llm
            )

            # 7. 计算置信度
            confidence = self._calculate_confidence(raw_elements, structured_data)

            return InterpretationResult(
                domain_id=self.domain_id,
                structured_data=structured_data,
                narrative=narrative,
                confidence=confidence,
                metadata={
                    "detail_level": detail_level,
                    "use_llm": use_llm,
                    "reading_order": reading_order,
                    "image_count": len(images),
                },
                raw_elements=raw_elements,
            )
        except DomainInterpretationError:
            raise
        except Exception as e:
            raise DomainInterpretationError(
                f"Failed to interpret comic document: {e}",
                domain_id=self.domain_id,
                stage="interpret",
                details={"error": str(e)},
            )

    async def _analyze_panels(
        self,
        image_data: bytes,
        detection: DetectionResult,
        config: dict | None = None
    ) -> list[dict]:
        """使用 VLM 分析每个分格"""
        panels: list[dict] = []
        
        for panel in detection.panels:
            try:
                # 裁剪分格图像
                panel_img = self._crop_panel(image_data, panel.bbox)
                
                if panel_img:
                    # 使用 VLM 描述场景
                    prompt = """请分析这个漫画分格，提供以下信息：
1. 场景描述：描述画面中发生的事情
2. 角色：列出画面中的角色（如果有）
3. 动作：描述角色正在做什么
4. 情绪：描述画面的情绪氛围

请以JSON格式返回：
{
    "scene_description": "场景描述",
    "characters": ["角色1", "角色2"],
    "action": "动作描述",
    "mood": "情绪氛围"
}"""
                    
                    response = await self._call_vlm(panel_img, prompt)
                    panel_info = self._parse_panel_response(response, panel.index)
                else:
                    panel_info = {
                        "index": panel.index,
                        "scene_description": "",
                        "characters": [],
                        "action": "",
                        "mood": "",
                    }
                
                panel_info["bbox"] = panel.bbox.to_dict()
                panel_info["confidence"] = panel.confidence
                panels.append(panel_info)
                
            except Exception as e:
                logger.warning(f"Failed to analyze panel {panel.index}: {e}")
                panels.append({
                    "index": panel.index,
                    "scene_description": "",
                    "characters": [],
                    "action": "",
                    "mood": "",
                    "bbox": panel.bbox.to_dict(),
                    "confidence": panel.confidence,
                    "error": str(e),
                })
        
        return panels

    def _crop_panel(self, image_data: bytes, bbox) -> bytes | None:
        """裁剪分格图像"""
        try:
            from PIL import Image
            import io
            
            img = Image.open(io.BytesIO(image_data))
            
            # 裁剪
            cropped = img.crop((bbox.x, bbox.y, bbox.x2, bbox.y2))
            
            # 转换为 bytes
            buffer = io.BytesIO()
            cropped.save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()
            
        except Exception as e:
            logger.warning(f"Failed to crop panel: {e}")
            return None

    def _parse_panel_response(self, response: str, panel_index: int) -> dict:
        """解析 VLM 对分格的分析响应"""
        import json
        
        result = {
            "index": panel_index,
            "scene_description": "",
            "characters": [],
            "action": "",
            "mood": "",
        }
        
        # 尝试提取 JSON
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response[start_idx:end_idx + 1]
            try:
                data = json.loads(json_str)
                result["scene_description"] = data.get("scene_description", "")
                result["characters"] = data.get("characters", [])
                result["action"] = data.get("action", "")
                result["mood"] = data.get("mood", "")
            except json.JSONDecodeError:
                # 如果 JSON 解析失败，使用原始响应作为场景描述
                result["scene_description"] = response.strip()
        else:
            result["scene_description"] = response.strip()
        
        return result

    async def _extract_dialogues(
        self,
        image_data: bytes,
        detection: DetectionResult,
        config: dict | None = None
    ) -> list[dict]:
        """提取对话文本"""
        dialogues: list[dict] = []
        
        # 如果没有检测到气泡，尝试整体 OCR
        if not detection.bubbles:
            try:
                prompt = """请识别这张漫画图片中的所有对话文字。
对于每段对话，请标注：
1. 对话内容
2. 说话者（如果能识别）
3. 对话类型（speech=对话, thought=心理活动, narration=旁白, sfx=音效）

请以JSON格式返回：
{
    "dialogues": [
        {"text": "对话内容", "speaker": "说话者", "type": "speech"},
        ...
    ]
}"""
                
                response = await self._call_vlm(image_data, prompt)
                dialogues = self._parse_dialogue_response(response)
                
            except Exception as e:
                logger.warning(f"Failed to extract dialogues: {e}")
        else:
            # 对每个气泡进行 OCR
            for bubble in detection.bubbles:
                try:
                    bubble_img = self._crop_panel(image_data, bubble.bbox)
                    if bubble_img:
                        prompt = "请识别这个对话气泡中的文字内容，只返回文字本身。"
                        text = await self._call_vlm(bubble_img, prompt)
                        
                        dialogues.append({
                            "text": text.strip(),
                            "speaker": "",
                            "panel_index": bubble.panel_index,
                            "bubble_type": bubble.bubble_type,
                        })
                except Exception as e:
                    logger.warning(f"Failed to OCR bubble: {e}")
        
        return dialogues

    def _parse_dialogue_response(self, response: str) -> list[dict]:
        """解析对话提取响应"""
        import json
        
        dialogues: list[dict] = []
        
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response[start_idx:end_idx + 1]
            try:
                data = json.loads(json_str)
                for d in data.get("dialogues", []):
                    dialogues.append({
                        "text": d.get("text", ""),
                        "speaker": d.get("speaker", ""),
                        "panel_index": d.get("panel_index", 0),
                        "bubble_type": d.get("type", "speech"),
                    })
            except json.JSONDecodeError:
                pass
        
        return dialogues

    async def _analyze_art_style(self, image_data: bytes) -> dict:
        """分析艺术风格"""
        try:
            prompt = """请分析这张漫画的艺术风格，包括：
1. 整体风格（如：日式漫画、美式漫画、欧式漫画、简笔画等）
2. 配色方案（如：黑白、彩色、单色调等）
3. 线条风格（如：粗犷、细腻、简洁等）
4. 其他特点

请以JSON格式返回：
{
    "style": "整体风格",
    "color_scheme": "配色方案",
    "line_work": "线条风格",
    "characteristics": ["特点1", "特点2"]
}"""
            
            response = await self._call_vlm(image_data, prompt)
            return self._parse_art_style_response(response)
            
        except Exception as e:
            logger.warning(f"Failed to analyze art style: {e}")
            return {}

    def _parse_art_style_response(self, response: str) -> dict:
        """解析艺术风格分析响应"""
        import json
        
        result = {
            "style": "",
            "color_scheme": "",
            "line_work": "",
            "characteristics": [],
        }
        
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response[start_idx:end_idx + 1]
            try:
                data = json.loads(json_str)
                result["style"] = data.get("style", "")
                result["color_scheme"] = data.get("color_scheme", "")
                result["line_work"] = data.get("line_work", "")
                result["characteristics"] = data.get("characteristics", [])
            except json.JSONDecodeError:
                result["style"] = response.strip()
        else:
            result["style"] = response.strip()
        
        return result

    def _build_structured_data(
        self,
        panels: list[dict],
        dialogues: list[dict],
        art_style: dict,
        detection: DetectionResult | None
    ) -> dict[str, Any]:
        """构建结构化数据"""
        structured: dict[str, Any] = {}
        
        # 分格数据
        structured["panel"] = panels
        structured["panel_count"] = len(panels)
        
        # 对话数据
        structured["dialogue"] = dialogues
        
        # 角色数据（从分格中提取）
        all_characters: set[str] = set()
        for panel in panels:
            for char in panel.get("characters", []):
                if char:
                    all_characters.add(char)
        
        structured["character"] = [
            {"name": name, "appearances": []}
            for name in all_characters
        ]
        
        # 艺术风格
        if art_style:
            structured["art_style"] = art_style
        
        # 阅读顺序
        if detection:
            structured["reading_order"] = detection.reading_order
        
        # 生成故事摘要
        structured["story_summary"] = self._generate_story_summary(panels, dialogues)
        structured["story_narrative"] = self._generate_story_narrative(panels, dialogues)
        
        return structured

    def _generate_story_summary(
        self,
        panels: list[dict],
        dialogues: list[dict]
    ) -> str:
        """生成故事摘要"""
        if not panels:
            return "无法识别故事内容"
        
        # 提取关键场景描述
        scenes = [p.get("scene_description", "") for p in panels if p.get("scene_description")]
        
        if scenes:
            return "；".join(scenes[:2]) + "..."
        
        return f"一个{len(panels)}格漫画故事"

    def _generate_story_narrative(
        self,
        panels: list[dict],
        dialogues: list[dict]
    ) -> str:
        """生成故事叙事"""
        if not panels:
            return ""
        
        narrative_parts: list[str] = []
        
        for panel in sorted(panels, key=lambda p: p.get("index", 0)):
            idx = panel.get("index", 0) + 1
            scene = panel.get("scene_description", "")
            action = panel.get("action", "")
            
            # 获取该分格的对话
            panel_dialogues = [
                d for d in dialogues
                if d.get("panel_index") == panel.get("index", 0)
            ]
            
            part = f"【第{idx}格】"
            if scene:
                part += f"\n{scene}"
            if action:
                part += f"\n动作：{action}"
            if panel_dialogues:
                for d in panel_dialogues:
                    speaker = d.get("speaker", "")
                    text = d.get("text", "")
                    if speaker:
                        part += f"\n{speaker}：「{text}」"
                    elif text:
                        part += f"\n「{text}」"
            
            narrative_parts.append(part)
        
        return "\n\n".join(narrative_parts)

    def _calculate_confidence(
        self,
        raw_elements: list[dict],
        structured_data: dict
    ) -> float:
        """计算解读置信度"""
        confidence = 0.0
        
        # 基础分：有分格数据
        panels = structured_data.get("panel", [])
        if panels:
            # 分格检测置信度
            panel_conf = sum(p.get("confidence", 0) for p in panels) / len(panels)
            confidence += panel_conf * 0.3
            
            # 场景描述完整性
            described = sum(1 for p in panels if p.get("scene_description"))
            confidence += (described / len(panels)) * 0.3
        
        # 对话提取
        dialogues = structured_data.get("dialogue", [])
        if dialogues:
            confidence += min(len(dialogues) * 0.05, 0.2)
        
        # 艺术风格分析
        if structured_data.get("art_style"):
            confidence += 0.1
        
        # 角色识别
        characters = structured_data.get("character", [])
        if characters:
            confidence += min(len(characters) * 0.05, 0.1)
        
        return min(confidence, 1.0)


def register_comic_domain() -> None:
    """注册漫画领域到全局注册表"""
    from core.domains.registry import get_domain_registry
    
    registry = get_domain_registry()
    interpreter = ComicInterpreter()
    
    registry.register(
        domain_id="comic",
        interpreter_class=ComicInterpreter,
        ontology=interpreter.get_ontology(),
        detection_patterns=[
            r"漫画",
            r"四格",
            r"comic",
            r"manga",
            r"分格",
            "file:.*\\.(jpg|jpeg|png|gif|webp)$",
        ]
    )
