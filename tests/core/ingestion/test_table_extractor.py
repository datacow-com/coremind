"""Tests for the TableExtractor capability."""

import pytest


class TestTableExtractor:
    """Tests for TableExtractor class."""

    def test_instantiation_default_config(self):
        """Test creating TableExtractor with default config."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()
        assert extractor.model == "table_transformer"
        assert extractor.output_format == "markdown"
        assert extractor.merge_cells is True

    def test_instantiation_custom_config(self):
        """Test creating TableExtractor with custom config."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        config = {
            "model": "pp_structure",
            "output_format": "csv",
            "merge_cells": False,
        }
        extractor = TableExtractor(config)

        assert extractor.model == "pp_structure"
        assert extractor.output_format == "csv"
        assert extractor.merge_cells is False

    def test_format_output_markdown(self):
        """Test formatting table data as Markdown."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor({"output_format": "markdown"})

        table_data = [
            ["Header1", "Header2", "Header3"],
            ["Row1-1", "Row1-2", "Row1-3"],
            ["Row2-1", "Row2-2", "Row2-3"],
        ]

        result = extractor._format_output(table_data)

        assert "| Header1 | Header2 | Header3 |" in result
        assert "|---|---|---|" in result
        assert "| Row1-1 | Row1-2 | Row1-3 |" in result

    def test_format_output_csv(self):
        """Test formatting table data as CSV."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor({"output_format": "csv"})

        table_data = [
            ["Name", "Age"],
            ["Alice", "30"],
            ["Bob", "25"],
        ]

        result = extractor._format_output(table_data, "csv")

        assert "Name,Age" in result
        assert "Alice,30" in result

    def test_format_output_json(self):
        """Test formatting table data as JSON."""
        import json

        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        table_data = [
            ["name", "value"],
            ["item1", "100"],
            ["item2", "200"],
        ]

        result = extractor._format_output(table_data, "json")
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "item1"
        assert parsed[0]["value"] == "100"

    def test_format_output_html(self):
        """Test formatting table data as HTML."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        table_data = [
            ["Col1", "Col2"],
            ["A", "B"],
        ]

        result = extractor._format_output(table_data, "html")

        assert "<table" in result
        assert "<th>Col1</th>" in result
        assert "<td>A</td>" in result
        assert "</table>" in result

    def test_format_output_empty(self):
        """Test formatting empty table data."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        result = extractor._format_output([])
        assert result == ""

    def test_cluster_by_y(self):
        """Test clustering text items by y-coordinate."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        items = [
            {"text": "A", "x": 10, "y": 10},
            {"text": "B", "x": 100, "y": 15},  # Same row as A
            {"text": "C", "x": 10, "y": 60},  # New row
            {"text": "D", "x": 100, "y": 65},  # Same row as C
        ]

        rows = extractor._cluster_by_y(items, threshold=20)

        assert len(rows) == 2
        assert len(rows[0]) == 2  # A and B
        assert len(rows[1]) == 2  # C and D

    @pytest.mark.asyncio
    async def test_structure_table_content(self):
        """Test parsing raw table content."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        # Tab-separated
        content = "Col1\tCol2\nVal1\tVal2"
        result = await extractor._structure_table_content(content)
        assert len(result) == 2
        assert result[0] == ["Col1", "Col2"]

        # Pipe-separated (Markdown)
        content = "| A | B |\n| 1 | 2 |"
        result = await extractor._structure_table_content(content)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_extract_no_tables(self):
        """Test extraction when no tables are present."""
        from core.ingestion.nodes.table_extractor import TableExtractor

        extractor = TableExtractor()

        state = {
            "parsed_blocks": [{"type": "text", "content": "Regular text"}],
            "images": [],
            "error_log": [],
        }

        result = await extractor.extract(state)

        # Should return state unchanged
        assert len(result["parsed_blocks"]) == 1
        assert result["parsed_blocks"][0]["type"] == "text"


class TestTableExtractorFactory:
    """Tests for factory function."""

    def test_create_table_extractor(self):
        """Test factory function creates extractor."""
        from core.ingestion.nodes.table_extractor import create_table_extractor

        extractor = create_table_extractor({"model": "camelot"})
        assert extractor.model == "camelot"

    def test_create_table_extractor_no_config(self):
        """Test factory function with no config."""
        from core.ingestion.nodes.table_extractor import create_table_extractor

        extractor = create_table_extractor()
        assert extractor is not None
        assert extractor.model == "table_transformer"
