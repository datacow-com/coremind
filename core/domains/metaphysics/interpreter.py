"""
Metaphysics Interpreter - 命理解读器

Phase 2: 垂直领域增强
实现命理文档的深度解读，支持八字、五行、神煞等元素的提取和分析。
"""
import re
import logging
from pathlib import Path
from typing import Any

from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError

logger = logging.getLogger(__name__)

# 天干地支常量
TIAN_GAN = "甲乙丙丁戊己庚辛壬癸"
DI_ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 五行映射
TIAN_GAN_WUXING = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}

DI_ZHI_WUXING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木",
    "辰": "土", "巳": "火", "午": "火", "未": "土",
    "申": "金", "酉": "金", "戌": "土", "亥": "水",
}

# 常见神煞
SHEN_SHA_LIST = [
    "天乙贵人", "文昌", "驿马", "桃花", "华盖", "将星",
    "羊刃", "禄神", "天德", "月德", "天医", "红鸾",
    "天喜", "孤辰", "寡宿", "劫煞", "亡神", "灾煞",
]


class MetaphysicsInterpreter(BaseDomainInterpreter):
    """
    命理解读器
    
    支持从文本和图像中提取命理元素（八字、五行、神煞等），
    并应用命理规则生成解读结果。
    """

    domain_id = "metaphysics"
    requires_gpu = True
    recommended_vram_mb = 4096

    def __init__(self):
        super().__init__()
        self._ontology: OntologySchema | None = None
        self._narrative_engine = None

    @property
    def narrative_engine(self):
        """延迟加载叙事引擎"""
        if self._narrative_engine is None:
            from core.domains.narrative_engine import NarrativeEngine
            self._narrative_engine = NarrativeEngine()
            # 注册命理领域模板
            self._register_templates()
        return self._narrative_engine

    def _register_templates(self) -> None:
        """注册命理叙事模板"""
        brief_template = "八字：{bazi.year_pillar}{bazi.month_pillar}{bazi.day_pillar}{bazi.hour_pillar}，五行{wuxing.dominant}旺。"
        
        detailed_template = """【八字命盘】
年柱：{bazi.year_pillar}  月柱：{bazi.month_pillar}
日柱：{bazi.day_pillar}  时柱：{bazi.hour_pillar}

【五行分析】
金：{wuxing.metal}  木：{wuxing.wood}  水：{wuxing.water}
火：{wuxing.fire}  土：{wuxing.earth}
五行{wuxing.dominant}旺，{wuxing.weak}弱。

【神煞】
{shen_sha}"""

        self._narrative_engine.register_template(self.domain_id, brief_template, "brief")
        self._narrative_engine.register_template(self.domain_id, detailed_template, "detailed")


    def get_ontology(self) -> OntologySchema:
        """获取命理本体定义"""
        if self._ontology is None:
            ontology_path = Path(__file__).parent / "ontology.yaml"
            if ontology_path.exists():
                self._ontology = OntologySchema.from_yaml(str(ontology_path))
            else:
                # 使用内置默认本体
                self._ontology = self._get_default_ontology()
        return self._ontology

    def _get_default_ontology(self) -> OntologySchema:
        """获取默认本体定义"""
        return OntologySchema.from_dict({
            "domain_id": "metaphysics",
            "version": "1.0",
            "entity_types": {
                "bazi": {
                    "description": "八字命盘",
                    "fields": {
                        "year_pillar": {"type": "string"},
                        "month_pillar": {"type": "string"},
                        "day_pillar": {"type": "string"},
                        "hour_pillar": {"type": "string"},
                    },
                    "required": ["year_pillar", "month_pillar", "day_pillar"],
                },
                "wuxing": {
                    "description": "五行分析",
                    "fields": {
                        "metal": {"type": "integer", "minimum": 0, "maximum": 8},
                        "wood": {"type": "integer", "minimum": 0, "maximum": 8},
                        "water": {"type": "integer", "minimum": 0, "maximum": 8},
                        "fire": {"type": "integer", "minimum": 0, "maximum": 8},
                        "earth": {"type": "integer", "minimum": 0, "maximum": 8},
                    },
                    "required": ["metal", "wood", "water", "fire", "earth"],
                },
            },
            "relationships": [
                {"name": "has_wuxing", "source_type": "bazi", "target_type": "wuxing", "cardinality": "one"},
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
        解读命理文档
        
        Args:
            document: 文档数据，包含 content, images, metadata 等
            config: 解读配置
                - detail_level: brief/detailed/comprehensive
                - use_llm: 是否使用 LLM 增强
                - extract_shen_sha: 是否提取神煞
                
        Returns:
            InterpretationResult: 解读结果
        """
        config = config or {}
        detail_level = config.get("detail_level", "detailed")
        use_llm = config.get("use_llm", True)
        extract_shen_sha = config.get("extract_shen_sha", True)

        try:
            # 1. 提取原始元素
            raw_elements = await self._extract_elements(document, config)
            
            # 2. 构建结构化数据
            structured_data = self._build_structured_data(raw_elements, extract_shen_sha)
            
            # 3. 应用命理规则
            structured_data = self._apply_rules(structured_data)
            
            # 4. 生成叙事文本
            narrative = await self.narrative_engine.generate(
                structured_data,
                self.domain_id,
                detail_level=detail_level,
                use_llm=use_llm
            )
            
            # 5. 计算置信度
            confidence = self._calculate_confidence(raw_elements, structured_data)
            
            return InterpretationResult(
                domain_id=self.domain_id,
                structured_data=structured_data,
                narrative=narrative,
                confidence=confidence,
                metadata={
                    "detail_level": detail_level,
                    "use_llm": use_llm,
                    "source_type": document.get("file_type", "unknown"),
                },
                raw_elements=raw_elements,
            )
        except Exception as e:
            raise DomainInterpretationError(
                f"Failed to interpret metaphysics document: {e}",
                domain_id=self.domain_id,
                stage="interpret",
                details={"error": str(e)},
            )


    async def _extract_elements(
        self,
        document: dict,
        config: dict | None = None
    ) -> list[dict]:
        """
        提取命理元素
        
        从文本和图像中提取八字、五行、神煞等元素。
        """
        raw_elements: list[dict] = []
        
        # 从文本提取
        content = document.get("content", "")
        if content:
            text_elements = self._extract_from_text(content)
            raw_elements.extend(text_elements)
        
        # 从图像提取（使用 VLM）
        images = document.get("images", [])
        for img_data in images:
            if isinstance(img_data, bytes):
                img_elements = await self._extract_from_image(img_data)
                raw_elements.extend(img_elements)
            elif isinstance(img_data, dict) and "data" in img_data:
                img_elements = await self._extract_from_image(img_data["data"])
                raw_elements.extend(img_elements)
        
        return raw_elements

    def _extract_from_text(self, content: str) -> list[dict]:
        """从文本中提取命理元素"""
        elements: list[dict] = []
        
        # 提取八字（四柱）
        bazi_elements = self._extract_bazi(content)
        elements.extend(bazi_elements)
        
        # 提取神煞
        shen_sha_elements = self._extract_shen_sha(content)
        elements.extend(shen_sha_elements)
        
        # 提取五行描述
        wuxing_elements = self._extract_wuxing_description(content)
        elements.extend(wuxing_elements)
        
        return elements

    def _extract_bazi(self, content: str) -> list[dict]:
        """提取八字（四柱）"""
        elements: list[dict] = []
        
        # 匹配干支组合
        gan_zhi_pattern = f"[{TIAN_GAN}][{DI_ZHI}]"
        matches = re.findall(gan_zhi_pattern, content)
        
        # 尝试识别四柱
        if len(matches) >= 4:
            # 假设前四个是年月日时柱
            elements.append({
                "type": "bazi",
                "year_pillar": matches[0],
                "month_pillar": matches[1],
                "day_pillar": matches[2],
                "hour_pillar": matches[3] if len(matches) > 3 else None,
                "source": "text_extraction",
            })
        elif len(matches) >= 3:
            elements.append({
                "type": "bazi",
                "year_pillar": matches[0],
                "month_pillar": matches[1],
                "day_pillar": matches[2],
                "hour_pillar": None,
                "source": "text_extraction",
            })
        
        # 尝试匹配标注格式：年柱：甲子
        pillar_patterns = [
            (r"年柱[：:]\s*([" + TIAN_GAN + "][" + DI_ZHI + "])", "year_pillar"),
            (r"月柱[：:]\s*([" + TIAN_GAN + "][" + DI_ZHI + "])", "month_pillar"),
            (r"日柱[：:]\s*([" + TIAN_GAN + "][" + DI_ZHI + "])", "day_pillar"),
            (r"时柱[：:]\s*([" + TIAN_GAN + "][" + DI_ZHI + "])", "hour_pillar"),
        ]
        
        labeled_bazi: dict[str, str] = {}
        for pattern, key in pillar_patterns:
            match = re.search(pattern, content)
            if match:
                labeled_bazi[key] = match.group(1)
        
        if labeled_bazi and len(labeled_bazi) >= 3:
            elements.append({
                "type": "bazi",
                **labeled_bazi,
                "source": "labeled_extraction",
            })
        
        return elements


    def _extract_shen_sha(self, content: str) -> list[dict]:
        """提取神煞"""
        elements: list[dict] = []
        
        for shen_sha in SHEN_SHA_LIST:
            if shen_sha in content:
                elements.append({
                    "type": "shen_sha",
                    "name": shen_sha,
                    "source": "text_extraction",
                })
        
        return elements

    def _extract_wuxing_description(self, content: str) -> list[dict]:
        """提取五行描述"""
        elements: list[dict] = []
        
        # 匹配五行数量描述：金2木3水1火1土1
        wuxing_pattern = r"金(\d+)[个]?木(\d+)[个]?水(\d+)[个]?火(\d+)[个]?土(\d+)"
        match = re.search(wuxing_pattern, content)
        if match:
            elements.append({
                "type": "wuxing",
                "metal": int(match.group(1)),
                "wood": int(match.group(2)),
                "water": int(match.group(3)),
                "fire": int(match.group(4)),
                "earth": int(match.group(5)),
                "source": "text_extraction",
            })
        
        # 匹配五行旺衰描述
        dominant_pattern = r"五行[以]?([金木水火土])旺"
        match = re.search(dominant_pattern, content)
        if match:
            elements.append({
                "type": "wuxing_dominant",
                "dominant": match.group(1),
                "source": "text_extraction",
            })
        
        return elements

    async def _extract_from_image(self, image_data: bytes) -> list[dict]:
        """使用 VLM 从图像中提取命理元素"""
        prompt = """请分析这张命理图像，提取以下信息：
1. 八字四柱（年柱、月柱、日柱、时柱）
2. 五行分布（金、木、水、火、土各多少）
3. 神煞（如天乙贵人、文昌、驿马等）

请以JSON格式返回，格式如下：
{
    "bazi": {"year_pillar": "甲子", "month_pillar": "乙丑", "day_pillar": "丙寅", "hour_pillar": "丁卯"},
    "wuxing": {"metal": 2, "wood": 3, "water": 1, "fire": 1, "earth": 1},
    "shen_sha": ["天乙贵人", "文昌"]
}

如果某项信息无法识别，请省略该字段。"""

        try:
            response = await self._call_vlm(image_data, prompt)
            return self._parse_vlm_response(response)
        except Exception as e:
            logger.warning(f"VLM extraction failed: {e}")
            return []


    def _parse_vlm_response(self, response: str) -> list[dict]:
        """解析 VLM 响应"""
        import json
        
        elements: list[dict] = []
        
        # 尝试提取 JSON - 使用更健壮的方法处理嵌套 JSON
        # 找到第一个 { 和最后一个 } 之间的内容
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            return elements
        
        json_str = response[start_idx:end_idx + 1]
        
        try:
            data = json.loads(json_str)
            
            # 提取八字
            if "bazi" in data:
                bazi = data["bazi"]
                elements.append({
                    "type": "bazi",
                    "year_pillar": bazi.get("year_pillar"),
                    "month_pillar": bazi.get("month_pillar"),
                    "day_pillar": bazi.get("day_pillar"),
                    "hour_pillar": bazi.get("hour_pillar"),
                    "source": "vlm_extraction",
                })
            
            # 提取五行
            if "wuxing" in data:
                wuxing = data["wuxing"]
                elements.append({
                    "type": "wuxing",
                    "metal": wuxing.get("metal", 0),
                    "wood": wuxing.get("wood", 0),
                    "water": wuxing.get("water", 0),
                    "fire": wuxing.get("fire", 0),
                    "earth": wuxing.get("earth", 0),
                    "source": "vlm_extraction",
                })
            
            # 提取神煞
            if "shen_sha" in data:
                for name in data["shen_sha"]:
                    elements.append({
                        "type": "shen_sha",
                        "name": name,
                        "source": "vlm_extraction",
                    })
        except json.JSONDecodeError:
            logger.warning("Failed to parse VLM response as JSON")
        
        return elements

    def _build_structured_data(
        self,
        raw_elements: list[dict],
        extract_shen_sha: bool = True
    ) -> dict[str, Any]:
        """构建结构化数据"""
        structured: dict[str, Any] = {}
        
        # 合并八字数据（优先使用标注提取，其次 VLM，最后文本提取）
        bazi_elements = [e for e in raw_elements if e.get("type") == "bazi"]
        if bazi_elements:
            # 按来源优先级排序
            priority = {"labeled_extraction": 0, "vlm_extraction": 1, "text_extraction": 2}
            bazi_elements.sort(key=lambda x: priority.get(x.get("source", ""), 3))
            best_bazi = bazi_elements[0]
            structured["bazi"] = {
                "year_pillar": best_bazi.get("year_pillar"),
                "month_pillar": best_bazi.get("month_pillar"),
                "day_pillar": best_bazi.get("day_pillar"),
                "hour_pillar": best_bazi.get("hour_pillar"),
            }

        
        # 合并五行数据
        wuxing_elements = [e for e in raw_elements if e.get("type") == "wuxing"]
        if wuxing_elements:
            best_wuxing = wuxing_elements[0]
            structured["wuxing"] = {
                "metal": best_wuxing.get("metal", 0),
                "wood": best_wuxing.get("wood", 0),
                "water": best_wuxing.get("water", 0),
                "fire": best_wuxing.get("fire", 0),
                "earth": best_wuxing.get("earth", 0),
            }
        elif "bazi" in structured:
            # 从八字计算五行
            structured["wuxing"] = self._calculate_wuxing_from_bazi(structured["bazi"])
        
        # 合并神煞数据
        if extract_shen_sha:
            shen_sha_elements = [e for e in raw_elements if e.get("type") == "shen_sha"]
            shen_sha_names = list(set(e.get("name") for e in shen_sha_elements if e.get("name")))
            if shen_sha_names:
                structured["shen_sha"] = shen_sha_names
        
        return structured

    def _calculate_wuxing_from_bazi(self, bazi: dict) -> dict[str, int]:
        """从八字计算五行分布"""
        wuxing_count = {"metal": 0, "wood": 0, "water": 0, "fire": 0, "earth": 0}
        wuxing_map = {"金": "metal", "木": "wood", "水": "water", "火": "fire", "土": "earth"}
        
        for pillar_key in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            pillar = bazi.get(pillar_key)
            if pillar and len(pillar) >= 2:
                # 天干五行
                tian_gan = pillar[0]
                if tian_gan in TIAN_GAN_WUXING:
                    wx = TIAN_GAN_WUXING[tian_gan]
                    wuxing_count[wuxing_map[wx]] += 1
                
                # 地支五行
                di_zhi = pillar[1]
                if di_zhi in DI_ZHI_WUXING:
                    wx = DI_ZHI_WUXING[di_zhi]
                    wuxing_count[wuxing_map[wx]] += 1
        
        return wuxing_count

    def _apply_rules(self, structured_data: dict) -> dict:
        """应用命理规则"""
        # 计算五行旺衰
        if "wuxing" in structured_data:
            wuxing = structured_data["wuxing"]
            wuxing_names = {"metal": "金", "wood": "木", "water": "水", "fire": "火", "earth": "土"}
            
            # 找出最旺和最弱的五行
            max_val = max(wuxing.values())
            min_val = min(wuxing.values())
            
            dominant = [wuxing_names[k] for k, v in wuxing.items() if v == max_val]
            weak = [wuxing_names[k] for k, v in wuxing.items() if v == min_val]
            
            structured_data["wuxing"]["dominant"] = "、".join(dominant)
            structured_data["wuxing"]["weak"] = "、".join(weak)
        
        return structured_data


    def _calculate_confidence(
        self,
        raw_elements: list[dict],
        structured_data: dict
    ) -> float:
        """计算解读置信度"""
        confidence = 0.0
        
        # 基础分：有八字数据
        if "bazi" in structured_data:
            bazi = structured_data["bazi"]
            # 四柱完整性
            pillar_count = sum(1 for k in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]
                              if bazi.get(k))
            confidence += pillar_count * 0.15  # 最多 0.6
        
        # 五行数据
        if "wuxing" in structured_data:
            confidence += 0.2
        
        # 神煞数据
        if "shen_sha" in structured_data and structured_data["shen_sha"]:
            confidence += min(len(structured_data["shen_sha"]) * 0.02, 0.1)
        
        # 多来源验证加分
        sources = set(e.get("source") for e in raw_elements)
        if len(sources) > 1:
            confidence += 0.1
        
        return min(confidence, 1.0)


def register_metaphysics_domain() -> None:
    """注册命理领域到全局注册表"""
    from core.domains.registry import get_domain_registry
    
    registry = get_domain_registry()
    interpreter = MetaphysicsInterpreter()
    
    registry.register(
        domain_id="metaphysics",
        interpreter_class=MetaphysicsInterpreter,
        ontology=interpreter.get_ontology(),
        detection_patterns=[
            r"八字",
            r"四柱",
            r"五行",
            r"命盘",
            r"天干地支",
            r"[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]",
        ]
    )
