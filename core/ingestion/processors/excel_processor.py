"""
Excel Processor - Intelligent Excel/CSV file analysis.

Features:
- Multi-sheet parsing
- Header detection
- Formula understanding
- Data relationship detection
- Large file handling
"""

import json
import logging
from typing import Any

from core.state import IngestState
from core.utils.monitor import ingest_duration

logger = logging.getLogger(__name__)


class ExcelProcessor:
    """
    Processes Excel and CSV files with intelligent analysis.

    This capability is part of the professional tier and supports:
    - XLSX, XLS, CSV files
    - Multi-sheet workbooks
    - Header auto-detection
    - Formula parsing (optional)
    - Cross-sheet relationship detection (optional)

    Configuration:
        parse_all_sheets: bool - Process all sheets
        header_detection: "auto" | "first_row" | "none"
        parse_formulas: bool - Understand formula logic
        detect_relations: bool - Find cross-sheet relationships
        max_rows: int - Maximum rows per sheet
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.parse_all_sheets = self.config.get("parse_all_sheets", True)
        self.header_detection = self.config.get("header_detection", "auto")
        self.parse_formulas = self.config.get("parse_formulas", False)
        self.detect_relations = self.config.get("detect_relations", False)
        self.max_rows = self.config.get("max_rows", 10000)

    async def __call__(self, state: IngestState) -> IngestState:
        """Process Excel file from state."""
        with ingest_duration.labels(stage="excel_processor").time():
            return await self.process(state)

    async def process(self, state: IngestState) -> IngestState:
        """Process Excel/CSV file and add parsed content to state."""
        file_path = state.get("file_path", "")
        file_type = state.get("file_type", "").lower()

        if file_type not in ("xlsx", "xls", "csv"):
            logger.debug(f"ExcelProcessor skipping non-Excel file: {file_type}")
            return state

        # Get raw content from state or load from path
        raw_content = state.get("raw_content")
        if not raw_content:
            try:
                from core.storage.blob_store import get_blob_store

                blob = get_blob_store()
                raw_content = await blob.get(file_path)
            except Exception as e:
                logger.error(f"Failed to load Excel file: {e}")
                state["error_log"].append(
                    {
                        "stage": "excel_processor",
                        "error": f"Failed to load file: {e}",
                    }
                )
                return state

        try:
            if file_type == "csv":
                sheets = await self._parse_csv(raw_content)
            else:
                sheets = await self._parse_excel(raw_content)

            # Convert sheets to parsed blocks
            parsed_blocks = []
            for sheet in sheets:
                block = self._sheet_to_block(sheet)
                parsed_blocks.append(block)

            # Detect relationships between sheets if enabled
            if self.detect_relations and len(sheets) > 1:
                relations = self._detect_sheet_relations(sheets)
                if relations:
                    parsed_blocks.append(
                        {
                            "type": "metadata",
                            "content": f"Sheet relationships:\n{json.dumps(relations, ensure_ascii=False, indent=2)}",
                            "metadata": {"type": "sheet_relations"},
                        }
                    )

            state["parsed_blocks"] = parsed_blocks
            state["extracted_text"] = "\n\n".join(
                block["content"] for block in parsed_blocks if block.get("content")
            )

        except Exception as e:
            logger.error(f"Excel processing failed: {e}")
            state["error_log"].append(
                {
                    "stage": "excel_processor",
                    "error": str(e),
                }
            )

        return state

    async def _parse_excel(self, content: bytes) -> list[dict[str, Any]]:
        """Parse Excel file into sheet structures."""
        try:
            from io import BytesIO

            import openpyxl

            wb = openpyxl.load_workbook(BytesIO(content), data_only=not self.parse_formulas)
            sheets = []

            sheet_names = wb.sheetnames if self.parse_all_sheets else [wb.sheetnames[0]]

            for sheet_name in sheet_names:
                ws = wb[sheet_name]
                sheet_data = self._extract_sheet_data(ws, sheet_name)
                sheets.append(sheet_data)

            return sheets

        except ImportError:
            logger.warning("openpyxl not installed, trying pandas fallback")
            return await self._parse_with_pandas(content, "xlsx")
        except Exception as e:
            logger.error(f"openpyxl parsing failed: {e}")
            raise

    async def _parse_csv(self, content: bytes) -> list[dict[str, Any]]:
        """Parse CSV file into sheet structure."""
        try:
            import csv
            from io import StringIO

            # Decode content
            text = content.decode("utf-8-sig")  # Handle BOM

            reader = csv.reader(StringIO(text))
            rows = list(reader)[: self.max_rows]

            # Detect header
            header = None
            data_start = 0
            if rows and self.header_detection != "none":
                if self.header_detection == "first_row":
                    header = rows[0]
                    data_start = 1
                elif self.header_detection == "auto":
                    header, data_start = self._auto_detect_header(rows)

            return [
                {
                    "name": "Sheet1",
                    "header": header,
                    "data": rows[data_start:],
                    "row_count": len(rows) - data_start,
                    "col_count": len(rows[0]) if rows else 0,
                }
            ]

        except Exception as e:
            logger.error(f"CSV parsing failed: {e}")
            raise

    async def _parse_with_pandas(self, content: bytes, file_type: str) -> list[dict[str, Any]]:
        """Fallback parsing using pandas."""
        try:
            from io import BytesIO

            import pandas as pd

            if file_type == "csv":
                df = pd.read_csv(BytesIO(content), nrows=self.max_rows)
                return [
                    {
                        "name": "Sheet1",
                        "header": list(df.columns),
                        "data": df.values.tolist(),
                        "row_count": len(df),
                        "col_count": len(df.columns),
                    }
                ]
            else:
                excel_file = pd.ExcelFile(BytesIO(content))
                sheets = []

                sheet_names = (
                    excel_file.sheet_names if self.parse_all_sheets else [excel_file.sheet_names[0]]
                )

                for name in sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=name, nrows=self.max_rows)
                    sheets.append(
                        {
                            "name": name,
                            "header": list(df.columns),
                            "data": df.values.tolist(),
                            "row_count": len(df),
                            "col_count": len(df.columns),
                        }
                    )

                return sheets

        except ImportError:
            raise ImportError("Neither openpyxl nor pandas is installed")

    def _extract_sheet_data(self, ws, sheet_name: str) -> dict[str, Any]:
        """Extract data from openpyxl worksheet."""
        rows = []
        formulas = [] if self.parse_formulas else None

        row_count = 0
        for row in ws.iter_rows(max_row=self.max_rows):
            row_values = []
            row_formulas = [] if self.parse_formulas else None

            for cell in row:
                # Get value
                value = cell.value if cell.value is not None else ""
                row_values.append(str(value))

                # Get formula if enabled
                if self.parse_formulas and row_formulas is not None:
                    if hasattr(cell, "value") and isinstance(cell.value, str):
                        if cell.value.startswith("="):
                            row_formulas.append(
                                {"cell": f"{cell.column_letter}{cell.row}", "formula": cell.value}
                            )

            if any(v for v in row_values):  # Skip empty rows
                rows.append(row_values)
                if self.parse_formulas and row_formulas:
                    formulas.extend(row_formulas)
                row_count += 1

        # Detect header
        header = None
        data_start = 0
        if rows and self.header_detection != "none":
            if self.header_detection == "first_row":
                header = rows[0]
                data_start = 1
            elif self.header_detection == "auto":
                header, data_start = self._auto_detect_header(rows)

        result = {
            "name": sheet_name,
            "header": header,
            "data": rows[data_start:],
            "row_count": row_count - data_start,
            "col_count": len(rows[0]) if rows else 0,
        }

        if formulas:
            result["formulas"] = formulas

        return result

    def _auto_detect_header(self, rows: list[list[str]]) -> tuple[list[str] | None, int]:
        """Auto-detect header row based on heuristics."""
        if not rows:
            return None, 0

        first_row = rows[0]

        # Heuristics for identifying header:
        # 1. First row has unique values
        # 2. First row is more text-like (not numeric)
        # 3. First row has shorter values than data rows

        is_header = True

        # Check if first row values look like headers
        for val in first_row:
            if not val:
                continue
            # If it's a pure number, probably not a header
            try:
                float(val.replace(",", "").replace(" ", ""))
                is_header = False
                break
            except ValueError:
                pass

        if is_header and len(first_row) == len(set(first_row)):
            return first_row, 1

        return None, 0

    def _sheet_to_block(self, sheet: dict[str, Any]) -> dict[str, Any]:
        """Convert sheet data to a parsed block."""
        lines = [f"## Sheet: {sheet['name']}\n"]

        header = sheet.get("header")
        data = sheet.get("data", [])

        # Create markdown table
        if header:
            lines.append("| " + " | ".join(str(h) for h in header) + " |")
            lines.append("|" + "|".join(["---"] * len(header)) + "|")

        for row in data[:100]:  # Limit preview rows
            # Pad row to match header length if needed
            if header:
                padded = list(row) + [""] * (len(header) - len(row))
                row = padded[: len(header)]
            lines.append("| " + " | ".join(str(c) for c in row) + " |")

        if len(data) > 100:
            lines.append(f"\n... and {len(data) - 100} more rows")

        # Add formula summary if present
        formulas = sheet.get("formulas", [])
        if formulas:
            lines.append("\n### Formulas:")
            for f in formulas[:10]:
                lines.append(f"- {f['cell']}: `{f['formula']}`")
            if len(formulas) > 10:
                lines.append(f"... and {len(formulas) - 10} more formulas")

        return {
            "type": "table",
            "content": "\n".join(lines),
            "page": 0,
            "metadata": {
                "sheet_name": sheet["name"],
                "row_count": sheet.get("row_count", 0),
                "col_count": sheet.get("col_count", 0),
                "has_formulas": bool(formulas),
                "source_type": "excel",
            },
        }

    def _detect_sheet_relations(self, sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Detect relationships between sheets based on common values/columns."""
        relations = []

        # Get column names for each sheet
        sheet_columns = {}
        sheet_values = {}

        for sheet in sheets:
            name = sheet["name"]
            header = sheet.get("header", [])
            if header:
                sheet_columns[name] = set(h.lower().strip() for h in header if h)

            # Get sample values from each column
            data = sheet.get("data", [])[:100]  # Sample first 100 rows
            values = {}
            for i, h in enumerate(header or []):
                col_values = set()
                for row in data:
                    if i < len(row) and row[i]:
                        col_values.add(str(row[i]).lower().strip())
                if col_values:
                    values[h] = col_values
            sheet_values[name] = values

        # Find common columns
        sheet_names = list(sheet_columns.keys())
        for i, name1 in enumerate(sheet_names):
            for name2 in sheet_names[i + 1 :]:
                common_cols = sheet_columns.get(name1, set()) & sheet_columns.get(name2, set())
                if common_cols:
                    relations.append(
                        {
                            "type": "common_columns",
                            "sheets": [name1, name2],
                            "columns": list(common_cols),
                        }
                    )

        return relations


# Factory function for capability loading
def create_excel_processor(config: dict[str, Any] | None = None) -> ExcelProcessor:
    """Factory function for creating ExcelProcessor instances."""
    return ExcelProcessor(config)
