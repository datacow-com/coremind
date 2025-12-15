"""
Panel Detector Tests - 分格检测器测试

Phase 2: 垂直领域增强
测试漫画分格检测和对话气泡检测功能。
Requirements: 6.1
"""
import pytest
from core.domains.comic.panel_detector import (
    PanelDetector,
    BoundingBox,
    Panel,
    SpeechBubble,
    DetectionResult,
)


class TestBoundingBox:
    """边界框测试"""

    def test_bounding_box_properties(self):
        """测试边界框属性计算"""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        
        assert bbox.x2 == 110
        assert bbox.y2 == 70
        assert bbox.center == (60, 45)
        assert bbox.area == 5000

    def test_bounding_box_to_dict(self):
        """测试边界框序列化"""
        bbox = BoundingBox(x=10, y=20, width=100, height=50)
        d = bbox.to_dict()
        
        assert d["x"] == 10
        assert d["y"] == 20
        assert d["width"] == 100
        assert d["height"] == 50


class TestPanel:
    """分格测试"""

    def test_panel_to_dict(self):
        """测试分格序列化"""
        panel = Panel(
            index=0,
            bbox=BoundingBox(x=0, y=0, width=400, height=400),
            confidence=0.9
        )
        d = panel.to_dict()
        
        assert d["index"] == 0
        assert d["confidence"] == 0.9
        assert "bbox" in d


class TestSpeechBubble:
    """对话气泡测试"""

    def test_speech_bubble_to_dict(self):
        """测试气泡序列化"""
        bubble = SpeechBubble(
            bbox=BoundingBox(x=50, y=50, width=80, height=40),
            panel_index=0,
            bubble_type="speech",
            confidence=0.8
        )
        d = bubble.to_dict()
        
        assert d["panel_index"] == 0
        assert d["bubble_type"] == "speech"
        assert d["confidence"] == 0.8


class TestDetectionResult:
    """检测结果测试"""

    def test_empty_detection_result(self):
        """测试空检测结果"""
        result = DetectionResult()
        
        assert result.panels == []
        assert result.bubbles == []
        assert result.reading_order == "ltr"

    def test_detection_result_to_dict(self):
        """测试检测结果序列化"""
        result = DetectionResult(
            panels=[Panel(index=0, bbox=BoundingBox(0, 0, 100, 100))],
            bubbles=[],
            reading_order="rtl",
            image_width=800,
            image_height=600,
        )
        d = result.to_dict()
        
        assert len(d["panels"]) == 1
        assert d["reading_order"] == "rtl"
        assert d["image_width"] == 800


class TestPanelDetector:
    """分格检测器测试"""

    def test_detector_initialization(self):
        """测试检测器初始化"""
        detector = PanelDetector()
        assert detector.reading_order == "auto"
        
        detector_rtl = PanelDetector(reading_order="rtl")
        assert detector_rtl.reading_order == "rtl"

    def test_detect_with_generated_image(self, four_panel_image):
        """测试使用生成图像进行检测"""
        detector = PanelDetector(reading_order="ltr")
        result = detector.detect(four_panel_image)
        
        assert isinstance(result, DetectionResult)
        assert result.image_width > 0
        assert result.image_height > 0
        # 应该检测到分格（可能是 4 个或回退的网格）
        assert len(result.panels) >= 1

    def test_detect_with_six_panel_image(self, six_panel_image):
        """测试六格漫画检测"""
        detector = PanelDetector(reading_order="ltr")
        result = detector.detect(six_panel_image)
        
        assert isinstance(result, DetectionResult)
        assert len(result.panels) >= 1

    def test_reading_order_ltr(self, four_panel_image):
        """测试从左到右阅读顺序"""
        detector = PanelDetector(reading_order="ltr")
        result = detector.detect(four_panel_image)
        
        # 验证分格按 LTR 顺序排列
        if len(result.panels) >= 2:
            # 同一行内，左边的分格索引应该更小
            panels_sorted = sorted(result.panels, key=lambda p: p.index)
            # 检查是否有合理的排序
            assert panels_sorted[0].index == 0

    def test_reading_order_rtl(self, four_panel_image):
        """测试从右到左阅读顺序"""
        detector = PanelDetector(reading_order="rtl")
        result = detector.detect(four_panel_image)
        
        assert result.reading_order == "rtl"

    def test_grid_fallback(self):
        """测试网格回退方案"""
        detector = PanelDetector()
        panels = detector._grid_fallback(800, 800)
        
        assert len(panels) == 4
        # 验证四格布局
        assert panels[0].bbox.x == 0
        assert panels[0].bbox.y == 0
        assert panels[1].bbox.x == 400
        assert panels[1].bbox.y == 0

    def test_sort_panels_ltr(self):
        """测试 LTR 分格排序"""
        detector = PanelDetector()
        
        panels = [
            Panel(index=0, bbox=BoundingBox(400, 0, 400, 400)),   # 右上
            Panel(index=0, bbox=BoundingBox(0, 0, 400, 400)),     # 左上
            Panel(index=0, bbox=BoundingBox(0, 400, 400, 400)),   # 左下
            Panel(index=0, bbox=BoundingBox(400, 400, 400, 400)), # 右下
        ]
        
        sorted_panels = detector._sort_panels(panels, "ltr", 800)
        
        # LTR: 左上 -> 右上 -> 左下 -> 右下
        assert sorted_panels[0].bbox.x == 0 and sorted_panels[0].bbox.y == 0
        assert sorted_panels[1].bbox.x == 400 and sorted_panels[1].bbox.y == 0

    def test_sort_panels_rtl(self):
        """测试 RTL 分格排序"""
        detector = PanelDetector()
        
        panels = [
            Panel(index=0, bbox=BoundingBox(400, 0, 400, 400)),   # 右上
            Panel(index=0, bbox=BoundingBox(0, 0, 400, 400)),     # 左上
            Panel(index=0, bbox=BoundingBox(0, 400, 400, 400)),   # 左下
            Panel(index=0, bbox=BoundingBox(400, 400, 400, 400)), # 右下
        ]
        
        sorted_panels = detector._sort_panels(panels, "rtl", 800)
        
        # RTL: 右上 -> 左上 -> 右下 -> 左下
        assert sorted_panels[0].bbox.x == 400 and sorted_panels[0].bbox.y == 0
        assert sorted_panels[1].bbox.x == 0 and sorted_panels[1].bbox.y == 0

    def test_find_containing_panel(self):
        """测试查找包含点的分格"""
        detector = PanelDetector()
        
        panels = [
            Panel(index=0, bbox=BoundingBox(0, 0, 400, 400)),
            Panel(index=1, bbox=BoundingBox(400, 0, 400, 400)),
        ]
        
        # 点在第一个分格内
        assert detector._find_containing_panel((200, 200), panels) == 0
        
        # 点在第二个分格内
        assert detector._find_containing_panel((600, 200), panels) == 1

    def test_invalid_image_data(self):
        """测试无效图像数据"""
        detector = PanelDetector()
        result = detector.detect(b"invalid image data")
        
        # 应该返回空结果而不是抛出异常
        assert isinstance(result, DetectionResult)

    def test_empty_image_data(self):
        """测试空图像数据"""
        detector = PanelDetector()
        result = detector.detect(b"")
        
        assert isinstance(result, DetectionResult)
        assert len(result.panels) == 0
