"""Tests for processor modules (Excel, Video, Comic)."""

import pytest


class TestExcelProcessor:
    """Tests for ExcelProcessor class."""

    def test_instantiation_default(self):
        """Test creating ExcelProcessor with default config."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        processor = ExcelProcessor()
        assert processor.parse_all_sheets is True
        assert processor.header_detection == "auto"
        assert processor.parse_formulas is False
        assert processor.detect_relations is False
        assert processor.max_rows == 10000

    def test_instantiation_custom(self):
        """Test creating ExcelProcessor with custom config."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        config = {
            "parse_all_sheets": False,
            "header_detection": "first_row",
            "parse_formulas": True,
            "max_rows": 5000,
        }
        processor = ExcelProcessor(config)

        assert processor.parse_all_sheets is False
        assert processor.header_detection == "first_row"
        assert processor.parse_formulas is True
        assert processor.max_rows == 5000

    def test_auto_detect_header_with_header(self):
        """Test auto-detecting header row."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        processor = ExcelProcessor()

        rows = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ]

        header, start = processor._auto_detect_header(rows)

        assert header == ["Name", "Age", "City"]
        assert start == 1

    def test_auto_detect_header_numeric_first_row(self):
        """Test auto-detect when first row is numeric."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        processor = ExcelProcessor()

        rows = [
            ["100", "200", "300"],
            ["150", "250", "350"],
        ]

        header, start = processor._auto_detect_header(rows)

        # Should not detect as header (all numeric)
        assert header is None
        assert start == 0

    def test_sheet_to_block(self):
        """Test converting sheet data to parsed block."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        processor = ExcelProcessor()

        sheet = {
            "name": "Sheet1",
            "header": ["A", "B"],
            "data": [["1", "2"], ["3", "4"]],
            "row_count": 2,
            "col_count": 2,
        }

        block = processor._sheet_to_block(sheet)

        assert block["type"] == "table"
        assert "Sheet1" in block["content"]
        assert "| A | B |" in block["content"]
        assert block["metadata"]["sheet_name"] == "Sheet1"

    def test_detect_sheet_relations(self):
        """Test detecting relationships between sheets."""
        from core.ingestion.processors.excel_processor import ExcelProcessor

        processor = ExcelProcessor({"detect_relations": True})

        sheets = [
            {
                "name": "Orders",
                "header": ["order_id", "customer_id", "amount"],
                "data": [["1", "C1", "100"]],
            },
            {
                "name": "Customers",
                "header": ["customer_id", "name", "email"],
                "data": [["C1", "Alice", "a@b.com"]],
            },
        ]

        relations = processor._detect_sheet_relations(sheets)

        assert len(relations) > 0
        assert any(r["type"] == "common_columns" for r in relations)
        # customer_id is common
        common_cols = [r for r in relations if r["type"] == "common_columns"]
        assert "customer_id" in common_cols[0]["columns"]


class TestVideoProcessor:
    """Tests for VideoProcessor class."""

    def test_instantiation_default(self):
        """Test creating VideoProcessor with default config."""
        from core.ingestion.processors.video_processor import VideoProcessor

        processor = VideoProcessor()
        assert processor.keyframe_interval == 10
        assert processor.transcription is True
        assert processor.whisper_model == "base"
        assert processor.frame_description is False
        assert processor.summarize is False

    def test_instantiation_custom(self):
        """Test creating VideoProcessor with custom config."""
        from core.ingestion.processors.video_processor import VideoProcessor

        config = {
            "keyframe_interval": 30,
            "transcription": False,
            "whisper_model": "large",
            "frame_description": True,
        }
        processor = VideoProcessor(config)

        assert processor.keyframe_interval == 30
        assert processor.transcription is False
        assert processor.whisper_model == "large"
        assert processor.frame_description is True

    def test_format_timestamp_seconds(self):
        """Test formatting timestamp for short videos."""
        from core.ingestion.processors.video_processor import VideoProcessor

        processor = VideoProcessor()

        assert processor._format_timestamp(0) == "00:00"
        assert processor._format_timestamp(65) == "01:05"
        assert processor._format_timestamp(125) == "02:05"

    def test_format_timestamp_hours(self):
        """Test formatting timestamp for long videos."""
        from core.ingestion.processors.video_processor import VideoProcessor

        processor = VideoProcessor()

        assert processor._format_timestamp(3665) == "01:01:05"
        assert processor._format_timestamp(7325) == "02:02:05"

    @pytest.mark.asyncio
    async def test_process_non_video(self):
        """Test processing non-video file type."""
        from core.ingestion.processors.video_processor import VideoProcessor

        processor = VideoProcessor()

        state = {
            "file_type": "pdf",
            "file_path": "test.pdf",
        }

        result = await processor.process(state)

        # Should return state unchanged for non-video
        assert result["file_type"] == "pdf"


class TestComicProcessor:
    """Tests for ComicProcessor class."""

    def test_instantiation_default(self):
        """Test creating ComicProcessor with default config."""
        from core.ingestion.processors.comic_processor import ComicProcessor

        processor = ComicProcessor()
        assert processor.panel_detection is True
        assert processor.bubble_ocr is True
        assert processor.scene_description is False
        assert processor.reading_order == "ltr"

    def test_instantiation_manga(self):
        """Test creating ComicProcessor for manga (RTL)."""
        from core.ingestion.processors.comic_processor import ComicProcessor

        config = {
            "reading_order": "rtl",
            "scene_description": True,
        }
        processor = ComicProcessor(config)

        assert processor.reading_order == "rtl"
        assert processor.scene_description is True

    def test_classify_bubble_speech(self):
        """Test classifying speech bubble."""
        from core.ingestion.processors.comic_processor import ComicProcessor

        processor = ComicProcessor()

        assert processor._classify_bubble("Hello there!") == "speech"
        assert processor._classify_bubble("How are you?") == "speech"

    def test_classify_bubble_sfx(self):
        """Test classifying sound effect."""
        from core.ingestion.processors.comic_processor import ComicProcessor

        processor = ComicProcessor()

        assert processor._classify_bubble("BAM!") == "sfx"
        assert processor._classify_bubble("POW*") == "sfx"

    def test_classify_bubble_narration(self):
        """Test classifying narration."""
        from core.ingestion.processors.comic_processor import ComicProcessor

        processor = ComicProcessor()

        assert processor._classify_bubble("Meanwhile, in the city...") == "narration"
        assert processor._classify_bubble("Later that day...") == "narration"

    def test_sort_panels_ltr(self):
        """Test sorting panels left-to-right."""
        from core.ingestion.processors.comic_processor import ComicProcessor, Panel

        processor = ComicProcessor({"reading_order": "ltr"})

        panels = [
            Panel(bbox=[200, 0, 400, 100], page=0, order=0),  # Right
            Panel(bbox=[0, 0, 200, 100], page=0, order=1),  # Left
            Panel(bbox=[0, 100, 200, 200], page=0, order=2),  # Bottom left
        ]

        sorted_panels = processor._sort_panels_on_page(panels)

        # First row: left (0,0) then right (200,0)
        assert sorted_panels[0].bbox[0] == 0  # Left panel first
        assert sorted_panels[1].bbox[0] == 200  # Right panel second

    def test_sort_panels_rtl(self):
        """Test sorting panels right-to-left (manga)."""
        from core.ingestion.processors.comic_processor import ComicProcessor, Panel

        processor = ComicProcessor({"reading_order": "rtl"})

        panels = [
            Panel(bbox=[0, 0, 200, 100], page=0, order=0),  # Left
            Panel(bbox=[200, 0, 400, 100], page=0, order=1),  # Right
        ]

        sorted_panels = processor._sort_panels_on_page(panels)

        # For RTL: right panel first
        assert sorted_panels[0].bbox[0] == 200  # Right panel first
        assert sorted_panels[1].bbox[0] == 0  # Left panel second

    def test_panels_to_blocks(self):
        """Test converting panels to parsed blocks."""
        from core.ingestion.processors.comic_processor import ComicProcessor, Panel, SpeechBubble

        processor = ComicProcessor()

        panel = Panel(bbox=[0, 0, 100, 100], page=0, order=0)
        panel.bubbles = [
            SpeechBubble(
                bbox=[10, 10, 50, 30],
                text="Hello!",
                bubble_type="speech",
            )
        ]
        panel.scene_description = "A character waving"

        blocks = processor._panels_to_blocks([panel])

        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert "Hello!" in blocks[0]["content"]
        assert "waving" in blocks[0]["content"]
        assert blocks[0]["metadata"]["panel_order"] == 0

    def test_extract_text_from_panels(self):
        """Test extracting plain text from panels."""
        from core.ingestion.processors.comic_processor import ComicProcessor, Panel, SpeechBubble

        processor = ComicProcessor()

        panels = [
            Panel(bbox=[0, 0, 100, 100], page=0, order=0),
            Panel(bbox=[0, 100, 100, 200], page=0, order=1),
        ]
        panels[0].bubbles = [SpeechBubble([0, 0, 10, 10], "First line", "speech")]
        panels[1].bubbles = [SpeechBubble([0, 0, 10, 10], "Second line", "speech")]

        text = processor._extract_text(panels)

        assert "First line" in text
        assert "Second line" in text
        assert "Page 1" in text  # 0-indexed internally, 1-indexed display


class TestProcessorFactoryFunctions:
    """Tests for processor factory functions."""

    def test_create_excel_processor(self):
        """Test Excel processor factory."""
        from core.ingestion.processors.excel_processor import create_excel_processor

        processor = create_excel_processor({"max_rows": 500})
        assert processor.max_rows == 500

    def test_create_video_processor(self):
        """Test Video processor factory."""
        from core.ingestion.processors.video_processor import create_video_processor

        processor = create_video_processor({"keyframe_interval": 5})
        assert processor.keyframe_interval == 5

    def test_create_comic_processor(self):
        """Test Comic processor factory."""
        from core.ingestion.processors.comic_processor import create_comic_processor

        processor = create_comic_processor({"reading_order": "rtl"})
        assert processor.reading_order == "rtl"
