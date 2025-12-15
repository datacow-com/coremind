"""
MetaphysicsInterpreter Unit Tests - 命理解读器单元测试

Phase 2: 垂直领域增强
测试命理解读器的核心功能。

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.domains.metaphysics.interpreter import (
    MetaphysicsInterpreter,
    TIAN_GAN,
    DI_ZHI,
    TIAN_GAN_WUXING,
    DI_ZHI_WUXING,
    SHEN_SHA_LIST,
)
from core.domains.base_interpreter import InterpretationResult


class TestMetaphysicsInterpreterInit:
    """测试解读器初始化"""

    def test_domain_id(self):
        """测试领域 ID"""
        interpreter = MetaphysicsInterpreter()
        assert interpreter.domain_id == "metaphysics"

    def test_requires_gpu(self):
        """测试 GPU 需求标记"""
        interpreter = MetaphysicsInterpreter()
        assert interpreter.requires_gpu is True
        assert interpreter.recommended_vram_mb == 4096

    def test_get_ontology(self):
        """测试获取本体定义"""
        interpreter = MetaphysicsInterpreter()
        ontology = interpreter.get_ontology()
        assert ontology is not None
        assert ontology.domain_id == "metaphysics"
        assert "bazi" in ontology.entity_types
        assert "wuxing" in ontology.entity_types


class TestBaziExtraction:
    """测试八字提取"""

    def test_extract_bazi_from_text(self):
        """测试从文本提取八字"""
        interpreter = MetaphysicsInterpreter()
        content = "甲子乙丑丙寅丁卯"
        elements = interpreter._extract_bazi(content)
        
        assert len(elements) >= 1
        bazi = elements[0]
        assert bazi["type"] == "bazi"
        assert bazi["year_pillar"] == "甲子"
        assert bazi["month_pillar"] == "乙丑"
        assert bazi["day_pillar"] == "丙寅"
        assert bazi["hour_pillar"] == "丁卯"


    def test_extract_bazi_labeled_format(self):
        """测试从标注格式提取八字"""
        interpreter = MetaphysicsInterpreter()
        content = "年柱：甲子\n月柱：乙丑\n日柱：丙寅\n时柱：丁卯"
        elements = interpreter._extract_bazi(content)
        
        # 应该有标注提取的结果
        labeled = [e for e in elements if e.get("source") == "labeled_extraction"]
        assert len(labeled) >= 1
        bazi = labeled[0]
        assert bazi["year_pillar"] == "甲子"
        assert bazi["month_pillar"] == "乙丑"
        assert bazi["day_pillar"] == "丙寅"
        assert bazi["hour_pillar"] == "丁卯"

    def test_extract_bazi_three_pillars(self):
        """测试提取三柱（无时柱）"""
        interpreter = MetaphysicsInterpreter()
        content = "庚申辛酉壬戌"
        elements = interpreter._extract_bazi(content)
        
        assert len(elements) >= 1
        bazi = elements[0]
        assert bazi["year_pillar"] == "庚申"
        assert bazi["month_pillar"] == "辛酉"
        assert bazi["day_pillar"] == "壬戌"

    def test_extract_bazi_empty_content(self):
        """测试空内容"""
        interpreter = MetaphysicsInterpreter()
        elements = interpreter._extract_bazi("")
        assert elements == []


class TestShenShaExtraction:
    """测试神煞提取"""

    def test_extract_shen_sha(self):
        """测试提取神煞"""
        interpreter = MetaphysicsInterpreter()
        content = "命带天乙贵人、文昌星照命"
        elements = interpreter._extract_shen_sha(content)
        
        names = [e["name"] for e in elements]
        assert "天乙贵人" in names
        assert "文昌" in names

    def test_extract_multiple_shen_sha(self):
        """测试提取多个神煞"""
        interpreter = MetaphysicsInterpreter()
        content = "孤辰寡宿劫煞并见"
        elements = interpreter._extract_shen_sha(content)
        
        names = [e["name"] for e in elements]
        assert "孤辰" in names
        assert "寡宿" in names
        assert "劫煞" in names

    def test_extract_no_shen_sha(self):
        """测试无神煞"""
        interpreter = MetaphysicsInterpreter()
        content = "普通文本内容"
        elements = interpreter._extract_shen_sha(content)
        assert elements == []


class TestWuxingExtraction:
    """测试五行提取"""

    def test_extract_wuxing_description(self):
        """测试提取五行描述"""
        interpreter = MetaphysicsInterpreter()
        content = "五行分布：金2木3水1火1土1"
        elements = interpreter._extract_wuxing_description(content)
        
        wuxing = [e for e in elements if e["type"] == "wuxing"]
        assert len(wuxing) >= 1
        assert wuxing[0]["metal"] == 2
        assert wuxing[0]["wood"] == 3
        assert wuxing[0]["water"] == 1
        assert wuxing[0]["fire"] == 1
        assert wuxing[0]["earth"] == 1

    def test_extract_wuxing_dominant(self):
        """测试提取五行旺衰"""
        interpreter = MetaphysicsInterpreter()
        content = "五行木旺"
        elements = interpreter._extract_wuxing_description(content)
        
        dominant = [e for e in elements if e["type"] == "wuxing_dominant"]
        assert len(dominant) >= 1
        assert dominant[0]["dominant"] == "木"



class TestWuxingCalculation:
    """测试五行计算"""

    def test_calculate_wuxing_from_bazi(self):
        """测试从八字计算五行"""
        interpreter = MetaphysicsInterpreter()
        bazi = {
            "year_pillar": "甲子",  # 木 + 水
            "month_pillar": "乙丑",  # 木 + 土
            "day_pillar": "丙寅",   # 火 + 木
            "hour_pillar": "丁卯",  # 火 + 木
        }
        wuxing = interpreter._calculate_wuxing_from_bazi(bazi)
        
        assert wuxing["wood"] == 4  # 甲、乙、寅、卯
        assert wuxing["water"] == 1  # 子
        assert wuxing["fire"] == 2   # 丙、丁
        assert wuxing["earth"] == 1  # 丑
        assert wuxing["metal"] == 0

    def test_calculate_wuxing_partial_bazi(self):
        """测试部分八字计算五行"""
        interpreter = MetaphysicsInterpreter()
        bazi = {
            "year_pillar": "庚申",  # 金 + 金
            "month_pillar": "辛酉",  # 金 + 金
            "day_pillar": "壬戌",   # 水 + 土
            "hour_pillar": None,
        }
        wuxing = interpreter._calculate_wuxing_from_bazi(bazi)
        
        assert wuxing["metal"] == 4  # 庚、辛、申、酉
        assert wuxing["water"] == 1  # 壬
        assert wuxing["earth"] == 1  # 戌


class TestRulesApplication:
    """测试规则应用"""

    def test_apply_rules_wuxing_dominant(self):
        """测试五行旺衰计算"""
        interpreter = MetaphysicsInterpreter()
        data = {
            "wuxing": {
                "metal": 0,
                "wood": 4,
                "water": 1,
                "fire": 2,
                "earth": 1,
            }
        }
        result = interpreter._apply_rules(data)
        
        assert result["wuxing"]["dominant"] == "木"
        assert result["wuxing"]["weak"] == "金"

    def test_apply_rules_multiple_dominant(self):
        """测试多个五行并旺"""
        interpreter = MetaphysicsInterpreter()
        data = {
            "wuxing": {
                "metal": 2,
                "wood": 2,
                "water": 2,
                "fire": 1,
                "earth": 1,
            }
        }
        result = interpreter._apply_rules(data)
        
        # 金、木、水并旺
        assert "金" in result["wuxing"]["dominant"]
        assert "木" in result["wuxing"]["dominant"]
        assert "水" in result["wuxing"]["dominant"]


class TestConfidenceCalculation:
    """测试置信度计算"""

    def test_confidence_full_bazi(self):
        """测试完整八字置信度"""
        interpreter = MetaphysicsInterpreter()
        raw_elements = [{"type": "bazi", "source": "text_extraction"}]
        structured_data = {
            "bazi": {
                "year_pillar": "甲子",
                "month_pillar": "乙丑",
                "day_pillar": "丙寅",
                "hour_pillar": "丁卯",
            },
            "wuxing": {"metal": 0, "wood": 4, "water": 1, "fire": 2, "earth": 1},
        }
        confidence = interpreter._calculate_confidence(raw_elements, structured_data)
        
        # 四柱完整 (0.6) + 五行 (0.2) = 0.8
        assert confidence >= 0.8

    def test_confidence_partial_bazi(self):
        """测试部分八字置信度"""
        interpreter = MetaphysicsInterpreter()
        raw_elements = [{"type": "bazi", "source": "text_extraction"}]
        structured_data = {
            "bazi": {
                "year_pillar": "甲子",
                "month_pillar": "乙丑",
                "day_pillar": "丙寅",
                "hour_pillar": None,
            },
        }
        confidence = interpreter._calculate_confidence(raw_elements, structured_data)
        
        # 三柱 (0.45)
        assert 0.4 <= confidence <= 0.5

    def test_confidence_with_shen_sha(self):
        """测试带神煞的置信度"""
        interpreter = MetaphysicsInterpreter()
        raw_elements = [{"type": "bazi", "source": "text_extraction"}]
        structured_data = {
            "bazi": {
                "year_pillar": "甲子",
                "month_pillar": "乙丑",
                "day_pillar": "丙寅",
                "hour_pillar": "丁卯",
            },
            "wuxing": {"metal": 0, "wood": 4, "water": 1, "fire": 2, "earth": 1},
            "shen_sha": ["天乙贵人", "文昌", "驿马"],
        }
        confidence = interpreter._calculate_confidence(raw_elements, structured_data)
        
        # 四柱 (0.6) + 五行 (0.2) + 神煞 (0.06) = 0.86
        assert confidence >= 0.85



class TestChineseCharacterHandling:
    """测试中文字符处理 - Requirements 5.5"""

    def test_simplified_chinese(self):
        """测试简体中文"""
        interpreter = MetaphysicsInterpreter()
        content = "年柱：甲子\n月柱：乙丑\n日柱：丙寅"
        elements = interpreter._extract_from_text(content)
        
        bazi = [e for e in elements if e["type"] == "bazi"]
        assert len(bazi) >= 1

    def test_traditional_chinese(self):
        """测试繁体中文"""
        interpreter = MetaphysicsInterpreter()
        # 繁体中文的天干地支与简体相同
        content = "年柱：甲子\n月柱：乙丑\n日柱：丙寅"
        elements = interpreter._extract_from_text(content)
        
        bazi = [e for e in elements if e["type"] == "bazi"]
        assert len(bazi) >= 1

    def test_mixed_punctuation(self):
        """测试混合标点"""
        interpreter = MetaphysicsInterpreter()
        # 中文冒号格式
        content = "年柱：甲子\n月柱：乙丑\n日柱：丙寅"
        elements = interpreter._extract_bazi(content)
        
        # 应该能提取标注格式
        labeled = [e for e in elements if e.get("source") == "labeled_extraction"]
        assert len(labeled) >= 1


class TestValidateOutput:
    """测试输出验证"""

    def test_validate_valid_output(self):
        """测试有效输出验证"""
        interpreter = MetaphysicsInterpreter()
        result = InterpretationResult(
            domain_id="metaphysics",
            structured_data={
                "bazi": {
                    "year_pillar": "甲子",
                    "month_pillar": "乙丑",
                    "day_pillar": "丙寅",
                    "hour_pillar": "丁卯",
                },
                "wuxing": {
                    "metal": 0,
                    "wood": 4,
                    "water": 1,
                    "fire": 2,
                    "earth": 1,
                },
            },
            narrative="测试叙事",
            confidence=0.8,
        )
        
        is_valid, violations = interpreter.validate_output(result)
        assert is_valid is True
        assert len(violations) == 0

    def test_validate_missing_required_field(self):
        """测试缺少必填字段"""
        interpreter = MetaphysicsInterpreter()
        result = InterpretationResult(
            domain_id="metaphysics",
            structured_data={
                "bazi": {
                    "year_pillar": "甲子",
                    # 缺少 month_pillar 和 day_pillar
                },
            },
            narrative="测试叙事",
            confidence=0.5,
        )
        
        is_valid, violations = interpreter.validate_output(result)
        assert is_valid is False
        assert len(violations) > 0


class TestInterpretAsync:
    """测试异步解读方法"""

    @pytest.mark.asyncio
    async def test_interpret_text_document(self):
        """测试解读文本文档"""
        interpreter = MetaphysicsInterpreter()
        
        # Mock the internal _narrative_engine attribute
        mock_engine = MagicMock()
        mock_engine.generate = AsyncMock(return_value="测试叙事文本")
        interpreter._narrative_engine = mock_engine
        
        document = {
            "content": "年柱：甲子\n月柱：乙丑\n日柱：丙寅\n时柱：丁卯\n五行金0木4水1火2土1",
            "file_type": "txt",
        }
        
        result = await interpreter.interpret(document, {"use_llm": False})
        
        assert result.domain_id == "metaphysics"
        assert "bazi" in result.structured_data
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_interpret_empty_document(self):
        """测试解读空文档"""
        interpreter = MetaphysicsInterpreter()
        
        # Mock the internal _narrative_engine attribute
        mock_engine = MagicMock()
        mock_engine.generate = AsyncMock(return_value="无法提取命理信息")
        interpreter._narrative_engine = mock_engine
        
        document = {"content": "", "file_type": "txt"}
        
        result = await interpreter.interpret(document, {"use_llm": False})
        
        assert result.domain_id == "metaphysics"
        assert result.confidence == 0.0


class TestVLMIntegration:
    """测试 VLM 集成 - Requirements 5.2"""

    def test_parse_vlm_response_valid(self):
        """测试解析有效 VLM 响应"""
        interpreter = MetaphysicsInterpreter()
        response = '''
        根据图像分析，提取到以下信息：
        {"bazi": {"year_pillar": "甲子", "month_pillar": "乙丑", "day_pillar": "丙寅"}, "wuxing": {"metal": 1, "wood": 3, "water": 2, "fire": 1, "earth": 1}, "shen_sha": ["文昌"]}
        '''
        
        elements = interpreter._parse_vlm_response(response)
        
        bazi = [e for e in elements if e["type"] == "bazi"]
        assert len(bazi) == 1
        assert bazi[0]["year_pillar"] == "甲子"
        
        wuxing = [e for e in elements if e["type"] == "wuxing"]
        assert len(wuxing) == 1
        assert wuxing[0]["wood"] == 3

    def test_parse_vlm_response_invalid(self):
        """测试解析无效 VLM 响应"""
        interpreter = MetaphysicsInterpreter()
        response = "无法识别图像中的命理信息"
        
        elements = interpreter._parse_vlm_response(response)
        assert elements == []
