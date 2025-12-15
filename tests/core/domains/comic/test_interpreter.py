"""
Comic Interpreter Tests - 漫画解读器测试

Phase 2: 垂直领域增强
测试漫画解读器的核心功能。
Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.domains.comic.interpreter import ComicInterpreter, register_comic_domain
from core.domains.base_interpreter import InterpretationResult
from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError


class TestComicInterpreterInit:
    """漫画解读器初始化测试"""

    def test_interpreter_attributes(self, comic_interpreter):
        """测试解读器属性"""
        assert comic_interpreter.domain_id == "comic"
        assert comic_interpreter.requires_gpu is True
        assert comic_interpreter.recommended_vram_mb == 8192

    def test_get_ontology(self, comic_interpreter):
        """测试获取本体定义"""
        ontology = comic_interpreter.get_ontology()
        
        assert isinstance(ontology, OntologySchema)
        assert ontology.domain_id == "comic"
        assert "panel" in ontology.entity_types
        assert "character" in ontology.entity_types
        assert "dialogue" in ontology.entity_types
        assert "art_style" in ontology.entity_types

    def test_ontology_panel_entity(self, comic_interpreter):
        """测试分格实体定义"""
        ontology = comic_interpreter.get_ontology()
        panel_type = ontology.entity_types["panel"]
        
        assert "index" in panel_type.fields
        assert "scene_description" in panel_type.fields
        assert "characters" in panel_type.fields
        assert "dialogue" in panel_type.fields

    def test_ontology_dialogue_entity(self, comic_interpreter):
        """测试对话实体定义"""
        ontology = comic_interpreter.get_ontology()
        dialogue_type = ontology.entity_types["dialogue"]
        
        assert "text" in dialogue_type.fields
        assert "speaker" in dialogue_type.fields
        assert "panel_index" in dialogue_type.fields
        assert "bubble_type" in dialogue_type.fields

    def test_panel_detector_lazy_loading(self, comic_interpreter):
        """测试分格检测器延迟加载"""
        # 初始时应该为 None
        assert comic_interpreter._panel_detector is None
        
        # 访问属性时应该创建实例
        detector = comic_interpreter.panel_detector
        assert detector is not None
        assert comic_interpreter._panel_detector is not None


class TestComicInterpreterValidation:
    """漫画解读器验证测试"""

    def test_validate_valid_output(self, comic_interpreter):
        """测试验证有效输出"""
        result = InterpretationResult(
            domain_id="comic",
            structured_data={
                "panel": [{"index": 0, "scene_description": "A scene"}],
                "dialogue": [{"text": "Hello", "panel_index": 0}],
            },
            narrative="Test narrative",
            confidence=0.8,
        )
        
        is_valid, violations = comic_interpreter.validate_output(result)
        assert is_valid is True
        assert len(violations) == 0

    def test_validate_missing_required_field(self, comic_interpreter):
        """测试验证缺少必填字段"""
        result = InterpretationResult(
            domain_id="comic",
            structured_data={
                "panel": [{"scene_description": "A scene"}],  # 缺少 index
            },
            narrative="Test narrative",
            confidence=0.8,
        )
        
        is_valid, violations = comic_interpreter.validate_output(result)
        assert is_valid is False
        assert any("index" in v for v in violations)


class TestComicInterpreterInterpret:
    """漫画解读器解读测试"""

    @pytest.mark.asyncio
    async def test_interpret_no_images(self, comic_interpreter):
        """测试解读无图像文档"""
        document = {"content": "text only", "metadata": {}}
        
        with pytest.raises(DomainInterpretationError) as exc_info:
            await comic_interpreter.interpret(document)
        
        assert "No images found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_interpret_with_mock_vlm(self, comic_interpreter, four_panel_image):
        """测试使用模拟 VLM 进行解读"""
        document = {
            "images": [four_panel_image],
            "metadata": {"domain": "comic"},
        }
        
        # 模拟 VLM 调用
        mock_vlm_response = '''{"scene_description": "A character standing", "characters": ["Character A"], "action": "standing", "mood": "neutral"}'''
        
        with patch.object(comic_interpreter, '_call_vlm', new_callable=AsyncMock) as mock_vlm:
            mock_vlm.return_value = mock_vlm_response
            
            result = await comic_interpreter.interpret(document, config={"use_llm": False})
        
        assert isinstance(result, InterpretationResult)
        assert result.domain_id == "comic"
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
        assert "panel" in result.structured_data

    @pytest.mark.asyncio
    async def test_interpret_with_config(self, comic_interpreter, four_panel_image):
        """测试使用配置进行解读"""
        document = {"images": [four_panel_image]}
        config = {
            "detail_level": "brief",
            "use_llm": False,
            "reading_order": "rtl",
            "analyze_art_style": False,
        }
        
        mock_vlm_response = '{"scene_description": "Test scene"}'
        
        with patch.object(comic_interpreter, '_call_vlm', new_callable=AsyncMock) as mock_vlm:
            mock_vlm.return_value = mock_vlm_response
            
            result = await comic_interpreter.interpret(document, config=config)
        
        assert result.metadata["detail_level"] == "brief"
        assert result.metadata["reading_order"] == "rtl"

    @pytest.mark.asyncio
    async def test_interpret_image_dict_format(self, comic_interpreter, four_panel_image):
        """测试图像字典格式"""
        document = {
            "images": [{"data": four_panel_image, "name": "test.jpg"}],
        }
        
        mock_vlm_response = '{"scene_description": "Test"}'
        
        with patch.object(comic_interpreter, '_call_vlm', new_callable=AsyncMock) as mock_vlm:
            mock_vlm.return_value = mock_vlm_response
            
            result = await comic_interpreter.interpret(document, config={"use_llm": False})
        
        assert isinstance(result, InterpretationResult)


class TestComicInterpreterPanelAnalysis:
    """分格分析测试"""

    def test_parse_panel_response_valid_json(self, comic_interpreter):
        """测试解析有效 JSON 响应"""
        response = '''{"scene_description": "A hero stands", "characters": ["Hero"], "action": "standing", "mood": "determined"}'''
        
        result = comic_interpreter._parse_panel_response(response, 0)
        
        assert result["index"] == 0
        assert result["scene_description"] == "A hero stands"
        assert result["characters"] == ["Hero"]
        assert result["action"] == "standing"
        assert result["mood"] == "determined"

    def test_parse_panel_response_with_prefix(self, comic_interpreter):
        """测试解析带前缀的 JSON 响应"""
        response = '''Here is the analysis: {"scene_description": "A scene", "characters": [], "action": "", "mood": ""}'''
        
        result = comic_interpreter._parse_panel_response(response, 1)
        
        assert result["index"] == 1
        assert result["scene_description"] == "A scene"

    def test_parse_panel_response_invalid_json(self, comic_interpreter):
        """测试解析无效 JSON 响应"""
        response = "This is just plain text without JSON"
        
        result = comic_interpreter._parse_panel_response(response, 2)
        
        assert result["index"] == 2
        assert result["scene_description"] == response.strip()
        assert result["characters"] == []


class TestComicInterpreterDialogueExtraction:
    """对话提取测试"""

    def test_parse_dialogue_response_valid(self, comic_interpreter):
        """测试解析有效对话响应"""
        response = '''{"dialogues": [{"text": "Hello!", "speaker": "A", "type": "speech"}, {"text": "Hi!", "speaker": "B", "type": "speech"}]}'''
        
        dialogues = comic_interpreter._parse_dialogue_response(response)
        
        assert len(dialogues) == 2
        assert dialogues[0]["text"] == "Hello!"
        assert dialogues[0]["speaker"] == "A"
        assert dialogues[1]["text"] == "Hi!"

    def test_parse_dialogue_response_empty(self, comic_interpreter):
        """测试解析空对话响应"""
        response = '''{"dialogues": []}'''
        
        dialogues = comic_interpreter._parse_dialogue_response(response)
        
        assert len(dialogues) == 0

    def test_parse_dialogue_response_invalid(self, comic_interpreter):
        """测试解析无效对话响应"""
        response = "No JSON here"
        
        dialogues = comic_interpreter._parse_dialogue_response(response)
        
        assert len(dialogues) == 0


class TestComicInterpreterArtStyle:
    """艺术风格分析测试"""

    def test_parse_art_style_response_valid(self, comic_interpreter):
        """测试解析有效艺术风格响应"""
        response = '''{"style": "manga", "color_scheme": "black_and_white", "line_work": "clean", "characteristics": ["detailed backgrounds"]}'''
        
        result = comic_interpreter._parse_art_style_response(response)
        
        assert result["style"] == "manga"
        assert result["color_scheme"] == "black_and_white"
        assert result["line_work"] == "clean"
        assert "detailed backgrounds" in result["characteristics"]

    def test_parse_art_style_response_invalid(self, comic_interpreter):
        """测试解析无效艺术风格响应"""
        response = "This is a manga style comic"
        
        result = comic_interpreter._parse_art_style_response(response)
        
        assert result["style"] == response.strip()


class TestComicInterpreterStructuredData:
    """结构化数据构建测试"""

    def test_build_structured_data(self, comic_interpreter):
        """测试构建结构化数据"""
        panels = [
            {"index": 0, "scene_description": "Scene 1", "characters": ["A", "B"]},
            {"index": 1, "scene_description": "Scene 2", "characters": ["A"]},
        ]
        dialogues = [
            {"text": "Hello", "speaker": "A", "panel_index": 0},
        ]
        art_style = {"style": "manga"}
        
        from core.domains.comic.panel_detector import DetectionResult
        detection = DetectionResult(reading_order="ltr")
        
        result = comic_interpreter._build_structured_data(panels, dialogues, art_style, detection)
        
        assert result["panel_count"] == 2
        assert len(result["panel"]) == 2
        assert len(result["dialogue"]) == 1
        assert result["reading_order"] == "ltr"
        # 角色应该被去重
        assert len(result["character"]) == 2

    def test_generate_story_summary(self, comic_interpreter):
        """测试生成故事摘要"""
        panels = [
            {"scene_description": "A hero appears"},
            {"scene_description": "The villain attacks"},
        ]
        
        summary = comic_interpreter._generate_story_summary(panels, [])
        
        assert "hero" in summary.lower() or "villain" in summary.lower()

    def test_generate_story_summary_empty(self, comic_interpreter):
        """测试空分格的故事摘要"""
        summary = comic_interpreter._generate_story_summary([], [])
        
        assert "无法识别" in summary

    def test_generate_story_narrative(self, comic_interpreter):
        """测试生成故事叙事"""
        panels = [
            {"index": 0, "scene_description": "Scene 1", "action": "walking"},
            {"index": 1, "scene_description": "Scene 2", "action": "running"},
        ]
        dialogues = [
            {"text": "Hello!", "speaker": "A", "panel_index": 0},
        ]
        
        narrative = comic_interpreter._generate_story_narrative(panels, dialogues)
        
        assert "第1格" in narrative
        assert "第2格" in narrative
        assert "Hello!" in narrative


class TestComicInterpreterConfidence:
    """置信度计算测试"""

    def test_calculate_confidence_full_data(self, comic_interpreter):
        """测试完整数据的置信度"""
        raw_elements = [{"type": "detection"}]
        structured_data = {
            "panel": [
                {"confidence": 0.9, "scene_description": "Scene"},
                {"confidence": 0.8, "scene_description": "Scene 2"},
            ],
            "dialogue": [{"text": "Hello"}],
            "art_style": {"style": "manga"},
            "character": [{"name": "A"}],
        }
        
        confidence = comic_interpreter._calculate_confidence(raw_elements, structured_data)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # 完整数据应该有较高置信度

    def test_calculate_confidence_minimal_data(self, comic_interpreter):
        """测试最小数据的置信度"""
        raw_elements = []
        structured_data = {
            "panel": [],
            "dialogue": [],
        }
        
        confidence = comic_interpreter._calculate_confidence(raw_elements, structured_data)
        
        assert confidence == 0.0


class TestComicDomainRegistration:
    """漫画领域注册测试"""

    def test_register_comic_domain(self):
        """测试注册漫画领域"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        
        # 重置注册表
        reset_domain_registry()
        registry = get_domain_registry()
        
        # 注册漫画领域
        register_comic_domain()
        
        # 验证注册
        assert registry.has_domain("comic")
        
        interpreter = registry.get_interpreter("comic")
        assert interpreter is not None
        assert interpreter.domain_id == "comic"
        
        # 清理
        reset_domain_registry()

    def test_domain_detection_patterns(self):
        """测试领域检测模式"""
        from core.domains.registry import get_domain_registry, reset_domain_registry
        
        reset_domain_registry()
        registry = get_domain_registry()
        register_comic_domain()
        
        # 测试检测
        doc_with_comic = {"content": "这是一个四格漫画"}
        detected = registry.detect_domain(doc_with_comic)
        assert detected == "comic"
        
        doc_with_manga = {"content": "This is a manga page"}
        detected = registry.detect_domain(doc_with_manga)
        assert detected == "comic"
        
        reset_domain_registry()
