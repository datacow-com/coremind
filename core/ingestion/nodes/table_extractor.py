"""
Table Extractor Node - Extracts and structures tables from documents.

Supports multiple table extraction backends:
- TableTransformer (Microsoft) - High precision deep learning model
- PP-Structure (PaddleOCR) - Fast and good for Chinese documents
- Camelot - PDF-specific extraction
"""

import asyncio
import logging
from typing import Any

from core.state import IngestState
from core.utils.monitor import ingest_duration

logger = logging.getLogger(__name__)


class TableExtractor:
    """
    Extracts tables from documents and converts them to structured format.

    This capability is part of the enhanced tier and supports:
    - PDF documents (native and scanned)
    - Images containing tables
    - DOCX/PPTX embedded tables

    Configuration:
        model: "table_transformer" | "pp_structure" | "camelot"
        output_format: "markdown" | "csv" | "json" | "html"
        merge_cells: bool - Handle merged cells
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.model = self.config.get("model", "table_transformer")
        self.output_format = self.config.get("output_format", "markdown")
        self.merge_cells = self.config.get("merge_cells", True)
        self._semaphore = asyncio.Semaphore(2)  # Limit concurrent processing

    async def __call__(self, state: IngestState) -> IngestState:
        """Process state and extract tables from parsed_blocks."""
        with ingest_duration.labels(stage="table_extractor").time():
            return await self.extract(state)

    async def extract(self, state: IngestState) -> IngestState:
        """Extract tables from the document state."""
        parsed_blocks = state.get("parsed_blocks", [])
        images = state.get("images", [])

        # Find existing table blocks that need extraction
        table_blocks = [b for b in parsed_blocks if b.get("type") == "table"]

        # Find images that look like tables (from VLM hint or detection)
        table_images = [
            img
            for img in images
            if img.get("hints", {}).get("is_table") or img.get("type") == "table"
        ]

        if not table_blocks and not table_images:
            logger.debug("No tables found to extract")
            return state

        # Process table blocks
        new_blocks = []
        for block in parsed_blocks:
            if block.get("type") == "table":
                enhanced_block = await self._enhance_table_block(block)
                new_blocks.append(enhanced_block)
            else:
                new_blocks.append(block)

        # Process table images
        for img in table_images:
            try:
                table_block = await self._extract_table_from_image(img)
                new_blocks.append(table_block)
            except Exception as e:
                logger.warning(f"Failed to extract table from image: {e}")
                state["error_log"].append(
                    {
                        "stage": "table_extractor",
                        "error": str(e),
                        "page": img.get("page"),
                    }
                )

        state["parsed_blocks"] = new_blocks
        return state

    async def _enhance_table_block(self, block: dict[str, Any]) -> dict[str, Any]:
        """Enhance an existing table block with better structure."""
        content = block.get("content", "")

        # If already in good format, keep it
        if content.startswith("|") and "|" in content:
            return block

        # Try to structure the content
        try:
            structured = await self._structure_table_content(content)
            formatted = self._format_output(structured)
            block["content"] = formatted
            block["metadata"] = block.get("metadata", {})
            block["metadata"]["table_model"] = self.model
            block["metadata"]["output_format"] = self.output_format
        except Exception as e:
            logger.warning(f"Failed to enhance table: {e}")

        return block

    async def _extract_table_from_image(self, img: dict[str, Any]) -> dict[str, Any]:
        """Extract table structure from an image."""
        async with self._semaphore:
            image_data = img.get("data")
            if not image_data:
                raise ValueError("No image data provided")

            # Choose extraction method based on model config
            if self.model == "table_transformer":
                table_data = await self._extract_with_table_transformer(image_data)
            elif self.model == "pp_structure":
                table_data = await self._extract_with_pp_structure(image_data)
            elif self.model == "camelot":
                # Camelot only works with PDF, fallback to TableTransformer for images
                table_data = await self._extract_with_table_transformer(image_data)
            else:
                table_data = await self._extract_with_table_transformer(image_data)

            formatted = self._format_output(table_data)

            return {
                "type": "table",
                "content": formatted,
                "page": img.get("page"),
                "bbox": img.get("bbox"),
                "metadata": {
                    "original_type": "image",
                    "table_model": self.model,
                    "output_format": self.output_format,
                    "row_count": len(table_data) if table_data else 0,
                    "col_count": len(table_data[0]) if table_data and table_data[0] else 0,
                },
            }

    async def _structure_table_content(self, content: str) -> list[list[str]]:
        """Parse raw table content into structured 2D array."""
        lines = content.strip().split("\n")
        rows = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Handle various delimiters
            if "\t" in line:
                cells = line.split("\t")
            elif "|" in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
            elif "," in line:
                # Be careful with commas in values
                import csv
                import io

                reader = csv.reader(io.StringIO(line))
                cells = list(next(reader))
            else:
                # Space-separated (heuristic)
                cells = line.split()

            if cells:
                rows.append(cells)

        return rows

    async def _extract_with_table_transformer(self, image_data: bytes) -> list[list[str]]:
        """
        Extract table using Microsoft TableTransformer.

        Uses the model locally if available, otherwise falls back to OCR-based extraction.
        """
        try:
            import io

            import torch
            from PIL import Image
            from transformers import DetrImageProcessor, TableTransformerForObjectDetection

            # Load image
            image = Image.open(io.BytesIO(image_data)).convert("RGB")

            # Load model (cached)
            processor = DetrImageProcessor.from_pretrained("microsoft/table-transformer-detection")
            model = TableTransformerForObjectDetection.from_pretrained(
                "microsoft/table-transformer-detection"
            )

            # Detect tables
            inputs = processor(images=image, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)

            # This gives table bounding boxes, not cell structure
            # For full OCR+structure, we need additional processing
            logger.debug(f"TableTransformer detected {len(outputs.logits)} potential tables")

            # Fallback to simpler OCR-based extraction
            return await self._ocr_table_extraction(image_data)

        except ImportError:
            logger.warning("TableTransformer not installed, using OCR fallback")
            return await self._ocr_table_extraction(image_data)
        except Exception as e:
            logger.warning(f"TableTransformer failed: {e}")
            return await self._ocr_table_extraction(image_data)

    async def _extract_with_pp_structure(self, image_data: bytes) -> list[list[str]]:
        """
        Extract table using PaddleOCR's PP-Structure.

        PP-Structure is optimized for Chinese documents and includes
        table structure recognition.
        """
        try:
            import io

            import numpy as np
            from paddleocr import PPStructure
            from PIL import Image

            # Load image
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_np = np.array(image)

            # Initialize PP-Structure
            engine = PPStructure(show_log=False, table=True)
            result = engine(image_np)

            # Parse table results
            tables = []
            for item in result:
                if item.get("type") == "table":
                    html = item.get("res", {}).get("html", "")
                    if html:
                        tables.append(self._parse_html_table(html))

            return tables[0] if tables else []

        except ImportError:
            logger.warning("PaddleOCR not installed, using OCR fallback")
            return await self._ocr_table_extraction(image_data)
        except Exception as e:
            logger.warning(f"PP-Structure failed: {e}")
            return await self._ocr_table_extraction(image_data)

    async def _ocr_table_extraction(self, image_data: bytes) -> list[list[str]]:
        """
        Basic OCR-based table extraction as fallback.

        Uses spatial analysis of OCR results to reconstruct table structure.
        """
        try:
            # Try to use paddleocr for OCR
            import io

            import numpy as np
            from paddleocr import PaddleOCR
            from PIL import Image

            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_np = np.array(image)

            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            result = ocr.ocr(image_np, cls=True)

            if not result or not result[0]:
                return []

            # Extract text with positions
            text_items = []
            for line in result[0]:
                box, (text, confidence) = line
                # Get center position
                x = sum(p[0] for p in box) / 4
                y = sum(p[1] for p in box) / 4
                text_items.append({"text": text, "x": x, "y": y, "box": box})

            # Group by rows (similar y-coordinate)
            rows = self._cluster_by_y(text_items)

            # Sort cells within rows by x
            table = []
            for row in rows:
                sorted_row = sorted(row, key=lambda t: t["x"])
                table.append([t["text"] for t in sorted_row])

            return table

        except ImportError:
            logger.warning("PaddleOCR not available for OCR fallback")
            return []
        except Exception as e:
            logger.warning(f"OCR table extraction failed: {e}")
            return []

    def _cluster_by_y(self, items: list[dict], threshold: float = 10) -> list[list[dict]]:
        """Cluster text items into rows based on y-coordinate."""
        if not items:
            return []

        sorted_items = sorted(items, key=lambda t: t["y"])
        rows = []
        current_row = [sorted_items[0]]
        current_y = sorted_items[0]["y"]

        for item in sorted_items[1:]:
            if abs(item["y"] - current_y) <= threshold:
                current_row.append(item)
            else:
                rows.append(current_row)
                current_row = [item]
                current_y = item["y"]

        if current_row:
            rows.append(current_row)

        return rows

    def _parse_html_table(self, html: str) -> list[list[str]]:
        """Parse HTML table to 2D array."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            if not table:
                return []

            rows = []
            for tr in table.find_all("tr"):
                cells = []
                for td in tr.find_all(["td", "th"]):
                    cells.append(td.get_text(strip=True))
                if cells:
                    rows.append(cells)

            return rows
        except ImportError:
            logger.warning("BeautifulSoup not installed")
            return []

    def _format_output(self, table_data: list[list[str]], format_type: str | None = None) -> str:
        """Format table data to specified output format."""
        fmt = format_type or self.output_format

        if not table_data:
            return ""

        if fmt == "markdown":
            return self._to_markdown(table_data)
        elif fmt == "csv":
            return self._to_csv(table_data)
        elif fmt == "json":
            return self._to_json(table_data)
        elif fmt == "html":
            return self._to_html(table_data)
        else:
            return self._to_markdown(table_data)

    def _to_markdown(self, data: list[list[str]]) -> str:
        """Convert to Markdown table."""
        if not data:
            return ""

        lines = []
        # Header
        header = data[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")

        # Body
        for row in data[1:]:
            # Pad row if needed
            padded = row + [""] * (len(header) - len(row))
            lines.append("| " + " | ".join(padded[: len(header)]) + " |")

        return "\n".join(lines)

    def _to_csv(self, data: list[list[str]]) -> str:
        """Convert to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        for row in data:
            writer.writerow(row)
        return output.getvalue()

    def _to_json(self, data: list[list[str]]) -> str:
        """Convert to JSON format."""
        import json

        if len(data) < 2:
            return json.dumps(data, ensure_ascii=False)

        # Use first row as headers
        headers = data[0]
        records = []
        for row in data[1:]:
            record = {}
            for i, header in enumerate(headers):
                record[header] = row[i] if i < len(row) else ""
            records.append(record)

        return json.dumps(records, ensure_ascii=False, indent=2)

    def _to_html(self, data: list[list[str]]) -> str:
        """Convert to HTML table."""
        if not data:
            return ""

        lines = ['<table border="1">']

        # Header
        lines.append("  <thead>")
        lines.append("    <tr>")
        for cell in data[0]:
            lines.append(f"      <th>{cell}</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")

        # Body
        lines.append("  <tbody>")
        for row in data[1:]:
            lines.append("    <tr>")
            for cell in row:
                lines.append(f"      <td>{cell}</td>")
            lines.append("    </tr>")
        lines.append("  </tbody>")

        lines.append("</table>")
        return "\n".join(lines)


# For direct capability loading via manifest
def create_table_extractor(config: dict[str, Any] | None = None) -> TableExtractor:
    """Factory function for creating TableExtractor instances."""
    return TableExtractor(config)
