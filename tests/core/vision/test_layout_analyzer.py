"""Tests for LayoutAnalyzer and vision modules."""

import pytest


class TestLayoutAnalyzer:
    """Tests for LayoutAnalyzer class."""

    def test_instantiation_default(self):
        """Test creating LayoutAnalyzer with default config."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        analyzer = LayoutAnalyzer()
        assert analyzer.model_name == "pp_structure"
        assert analyzer.detect_reading_order is True

    def test_instantiation_custom(self):
        """Test creating LayoutAnalyzer with custom config."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        config = {
            "model": "yolo_doclayout",
            "detect_reading_order": False,
        }
        analyzer = LayoutAnalyzer(config)

        assert analyzer.model_name == "yolo_doclayout"
        assert analyzer.detect_reading_order is False

    def test_model_configs_defined(self):
        """Test that model configurations are properly defined."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        assert "yolo_doclayout" in LayoutAnalyzer.MODEL_CONFIGS
        assert "layoutlmv3" in LayoutAnalyzer.MODEL_CONFIGS
        assert "dit" in LayoutAnalyzer.MODEL_CONFIGS
        assert "pp_structure" in LayoutAnalyzer.MODEL_CONFIGS

        for model, config in LayoutAnalyzer.MODEL_CONFIGS.items():
            assert "description" in config
            assert "input_size" in config
            assert "labels" in config

    def test_normalize_type(self):
        """Test normalizing layout type labels."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        analyzer = LayoutAnalyzer()

        assert analyzer._normalize_type("TEXT") == "text"
        assert analyzer._normalize_type("paragraph") == "text"
        assert analyzer._normalize_type("Title") == "title"
        assert analyzer._normalize_type("HEADING") == "title"
        assert analyzer._normalize_type("TABLE") == "table"
        assert analyzer._normalize_type("image") == "figure"
        assert analyzer._normalize_type("unknown_type") == "text"

    def test_map_layout_type(self):
        """Test mapping layout type to block type."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        analyzer = LayoutAnalyzer()

        assert analyzer._map_layout_type("title") == "header"
        assert analyzer._map_layout_type("text") == "text"
        assert analyzer._map_layout_type("table") == "table"
        assert analyzer._map_layout_type("figure") == "image"
        assert analyzer._map_layout_type("footer") == "footer"

    def test_detect_reading_order_impl(self):
        """Test reading order detection."""
        from core.vision.layout_analyzer import LayoutAnalyzer, LayoutElement

        analyzer = LayoutAnalyzer()

        # Create elements not in reading order
        elements = [
            LayoutElement("text", [100, 0, 200, 50], 0.9, 0),  # Right, top
            LayoutElement("text", [0, 0, 100, 50], 0.9, 0),  # Left, top
            LayoutElement("text", [0, 100, 100, 150], 0.9, 0),  # Left, bottom
        ]

        sorted_elements = analyzer._detect_reading_order_impl(elements)

        # Should be sorted: top-left, top-right, bottom-left
        assert sorted_elements[0].bbox[0] == 0  # First is left
        assert sorted_elements[1].bbox[0] == 100  # Second is right (same row)
        assert sorted_elements[2].bbox[1] == 100  # Third is bottom row

    def test_sort_by_reading_order(self):
        """Test sorting elements by reading order across pages."""
        from core.vision.layout_analyzer import LayoutAnalyzer, LayoutElement

        analyzer = LayoutAnalyzer()

        elements = [
            LayoutElement("text", [0, 0, 100, 50], 0.9, page=1, order=0),
            LayoutElement("text", [0, 0, 100, 50], 0.9, page=0, order=1),
            LayoutElement("text", [0, 0, 100, 50], 0.9, page=0, order=0),
        ]

        sorted_elements = analyzer._sort_by_reading_order(elements)

        # Page 0 first, then page 1
        assert sorted_elements[0].page == 0
        assert sorted_elements[0].order == 0
        assert sorted_elements[1].page == 0
        assert sorted_elements[1].order == 1
        assert sorted_elements[2].page == 1

    @pytest.mark.asyncio
    async def test_analyze_no_images(self):
        """Test analyze with no images."""
        from core.vision.layout_analyzer import LayoutAnalyzer

        analyzer = LayoutAnalyzer()

        state = {
            "images": [],
            "parsed_blocks": [],
        }

        result = await analyzer.analyze(state)

        assert result["parsed_blocks"] == []


class TestLayoutElement:
    """Tests for LayoutElement class."""

    def test_layout_element_creation(self):
        """Test creating a LayoutElement."""
        from core.vision.layout_analyzer import LayoutElement

        elem = LayoutElement(
            element_type="title",
            bbox=[10, 20, 100, 50],
            confidence=0.95,
            page=0,
            content="Chapter 1",
            order=0,
        )

        assert elem.type == "title"
        assert elem.bbox == [10, 20, 100, 50]
        assert elem.confidence == 0.95
        assert elem.page == 0
        assert elem.content == "Chapter 1"
        assert elem.order == 0

    def test_layout_element_to_dict(self):
        """Test converting LayoutElement to dict."""
        from core.vision.layout_analyzer import LayoutElement

        elem = LayoutElement(
            element_type="table",
            bbox=[0, 0, 200, 100],
            confidence=0.88,
            page=2,
        )

        d = elem.to_dict()

        assert d["type"] == "table"
        assert d["bbox"] == [0, 0, 200, 100]
        assert d["confidence"] == 0.88
        assert d["page"] == 2
        assert d["content"] is None
        assert d["order"] is None


class TestAnalyzeBlocks:
    """Tests for the legacy analyze_blocks function."""

    def test_analyze_blocks_import(self):
        """Test that analyze_blocks can be imported."""
        from core.vision.layout_analyzer import analyze_blocks

        assert callable(analyze_blocks)

    def test_analyze_blocks_empty_returns_empty(self):
        """Test that invalid input returns empty list."""
        from core.vision.layout_analyzer import analyze_blocks

        # Invalid image bytes should return empty
        result = analyze_blocks(b"not an image")
        assert result == []

    @pytest.mark.skipif(True, reason="Requires OpenCV and valid image")
    def test_analyze_blocks_with_image(self):
        """Test analyze_blocks with a real image."""
        # This test would need a real image and OpenCV installed
        pass


class TestLayoutAnalyzerFactory:
    """Tests for factory function."""

    def test_create_layout_analyzer(self):
        """Test factory function creates analyzer."""
        from core.vision.layout_analyzer import create_layout_analyzer

        analyzer = create_layout_analyzer({"model": "opencv"})
        assert analyzer.model_name == "opencv"

    def test_create_layout_analyzer_no_config(self):
        """Test factory function with no config."""
        from core.vision.layout_analyzer import create_layout_analyzer

        analyzer = create_layout_analyzer()
        assert analyzer is not None
        assert analyzer.model_name == "pp_structure"
