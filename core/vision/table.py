from typing import Any


class TableExtractor:
    def __init__(self):
        # 可以在此注入表格检测/解析模型
        pass

    def extract_from_text(self, text: str) -> list[dict[str, Any]]:
        """
        Extract Markdown tables from text using heuristics.
        Returns list of {content: str, type: 'table', bbox: None}
        """
        tables = []
        lines = text.split("\n")
        in_table = False
        current_table = []

        for line in lines:
            if line.strip().startswith("|") and line.strip().endswith("|"):
                if not in_table:
                    # Potential start
                    in_table = True
                    current_table = [line]
                else:
                    current_table.append(line)
            else:
                if in_table:
                    # End of table
                    if len(current_table) >= 2:  # At least header and separator or row
                        tables.append(
                            {"type": "table", "content": "\n".join(current_table), "bbox": None}
                        )
                    in_table = False
                    current_table = []

        if in_table and len(current_table) >= 2:
            tables.append({"type": "table", "content": "\n".join(current_table), "bbox": None})

        return tables

    def extract_from_blocks(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Identify table blocks from parsed Layout blocks.
        """
        tables = []
        for block in blocks:
            if block.get("type") == "table":
                tables.append(block)
        return tables

    def to_csv(self, md_table: str) -> str:
        """Convert MD table to CSV for better embedding semantic"""
        try:
            lines = [l.strip() for l in md_table.strip().split("\n") if l.strip()]
            if len(lines) < 2:
                return md_table

            # Filter separator line
            filtered = [l for l in lines if not set(l.replace("|", "").strip()) <= set(":-")]

            csv_lines = []
            for line in filtered:
                # Naive split
                cells = [c.strip() for c in line.split("|")[1:-1]]
                csv_lines.append(",".join(cells))
            return "\n".join(csv_lines)
        except:
            return md_table
