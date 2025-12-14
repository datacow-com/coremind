"""
CPU-based text parser for various document formats.

Supports: PDF, Markdown, HTML, Email, DOCX, PPTX
"""

import email
import io
from email import policy
from html.parser import HTMLParser

import fitz  # PyMuPDF

from core.state import IngestState
from core.utils.monitor import ingest_duration


class _HtmlTextExtractor(HTMLParser):
    """Extract text from HTML while preserving basic structure."""

    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"h1", "h2", "h3"}:
            self.texts.append("\n# ")
        elif tag in {"li"}:
            self.texts.append("\n- ")
        elif tag in {"p"}:
            self.texts.append("\n\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.texts.append(data.strip())


class CpuTextParser:
    """
    CPU-based parser for text extraction from various formats.

    Supported formats:
    - PDF (via PyMuPDF)
    - Markdown
    - HTML
    - Email (.eml)
    - DOCX (via python-docx)
    - PPTX (via python-pptx)
    """

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage="cpu_parser").time():
            content = state.get("raw_content")
            local_path = None
            
            # P1 Fix: Support lazy loading - use local_temp_path for streaming
            if not content and state.get("lazy_load") and state.get("local_temp_path"):
                local_path = state["local_temp_path"]
            
            if not content and not local_path:
                return state

            file_type = state["file_type"].lower()
            blocks = []

            try:
                if file_type == "pdf":
                    # Use streaming for lazy-loaded PDFs to reduce memory
                    if local_path:
                        blocks = self._parse_pdf_streaming(local_path)
                    else:
                        blocks = self._parse_pdf(content)

                elif file_type in ("md", "markdown"):
                    # For non-PDF types with lazy loading, read file content
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_markdown(content)

                elif file_type in ("html", "htm"):
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_html(content)

                elif file_type == "eml":
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_email(content)

                elif file_type in ("docx", "doc"):
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_docx(content)

                elif file_type in ("pptx", "ppt"):
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_pptx(content)

                elif file_type == "txt":
                    if local_path and not content:
                        with open(local_path, "rb") as f:
                            content = f.read()
                    blocks = self._parse_text(content)

            except Exception as e:
                state["error_log"].append(
                    {"stage": "cpu_parser", "error": str(e), "file_type": file_type}
                )

            state["parsed_blocks"] = blocks
            return state

    def _parse_pdf_streaming(self, file_path: str) -> list:
        """
        Parse PDF from file path using PyMuPDF with streaming.
        
        P1 Fix: Memory-efficient parsing for large files.
        Opens file directly instead of loading into memory.
        Processes one page at a time to minimize memory footprint.
        """
        blocks = []
        # Open directly from file path - PyMuPDF handles streaming internally
        with fitz.open(file_path) as doc:
            for page_num, page in enumerate(doc):
                # Process page and immediately release
                page_blocks = self._extract_page_content(page, page_num)
                blocks.extend(page_blocks)
                # Explicitly clear page to help GC
                page = None
        return blocks

    def _extract_page_content(self, page, page_num: int) -> list:
        """Extract content from a single page."""
        blocks = []
        
        # Extract text blocks
        text_blocks = page.get_text("blocks")
        for b in text_blocks:
            if b[6] == 0:  # text block
                blocks.append({
                    "type": "text",
                    "content": b[4],
                    "bbox": [b[0], b[1], b[2], b[3]],
                    "page": page_num + 1,
                })
        
        # Extract tables
        try:
            tables = page.find_tables()
            for table_idx, table in enumerate(tables):
                table_data = table.extract()
                if table_data:
                    md_table = self._table_to_markdown(table_data)
                    if md_table.strip():
                        blocks.append({
                            "type": "table",
                            "content": md_table,
                            "bbox": list(table.bbox) if hasattr(table, 'bbox') else None,
                            "page": page_num + 1,
                            "table_index": table_idx,
                            "row_count": len(table_data),
                            "col_count": len(table_data[0]) if table_data else 0,
                        })
        except (AttributeError, Exception):
            pass
        
        return blocks

    def _parse_pdf(self, content: bytes) -> list:
        """
        Parse PDF using PyMuPDF.
        
        P1 Fix: Added table detection using PyMuPDF's find_tables() method.
        """
        blocks = []
        with fitz.open(stream=content, filetype="pdf") as doc:
            for page_num, page in enumerate(doc):
                # Extract text blocks
                text_blocks = page.get_text("blocks")
                for b in text_blocks:
                    # (x0, y0, x1, y1, "text", block_no, block_type)
                    # block_type: 0 = text, 1 = image
                    if b[6] == 0:  # text
                        blocks.append(
                            {
                                "type": "text",
                                "content": b[4],
                                "bbox": [b[0], b[1], b[2], b[3]],
                                "page": page_num + 1,
                            }
                        )
                
                # P1 Fix: Extract tables using PyMuPDF's table detection
                try:
                    tables = page.find_tables()
                    for table_idx, table in enumerate(tables):
                        # Extract table data
                        table_data = table.extract()
                        if table_data:
                            # Convert to Markdown format
                            md_table = self._table_to_markdown(table_data)
                            if md_table.strip():
                                blocks.append(
                                    {
                                        "type": "table",
                                        "content": md_table,
                                        "bbox": list(table.bbox) if hasattr(table, 'bbox') else None,
                                        "page": page_num + 1,
                                        "table_index": table_idx,
                                        "row_count": len(table_data),
                                        "col_count": len(table_data[0]) if table_data else 0,
                                    }
                                )
                except AttributeError:
                    # find_tables() not available in older PyMuPDF versions
                    pass
                except Exception:
                    # Table detection failed, continue with text extraction
                    pass
                    
        return blocks

    def _parse_markdown(self, content: bytes) -> list:
        """Parse Markdown file."""
        text = content.decode("utf-8", errors="ignore")
        blocks = []
        paras = text.split("\n\n")
        for p in paras:
            if p.strip():
                blocks.append({"type": "text", "content": p.strip(), "page": 1, "bbox": None})
        return blocks

    def _parse_html(self, content: bytes) -> list:
        """Parse HTML file."""
        text = content.decode("utf-8", errors="ignore")
        parser = _HtmlTextExtractor()
        parser.feed(text)
        full_text = "".join(parser.texts)

        blocks = []
        paras = full_text.split("\n\n")
        for p in paras:
            if p.strip():
                blocks.append({"type": "text", "content": p.strip(), "page": 1, "bbox": None})
        return blocks

    def _parse_email(self, content: bytes) -> list:
        """Parse email (.eml) file."""
        msg = email.message_from_bytes(content, policy=policy.default)
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    body = part.get_content()
                    break
        else:
            body = msg.get_content()

        return [
            {
                "type": "text",
                "content": f"Subject: {msg.get('subject')}\nFrom: {msg.get('from')}\n\n{body}",
                "page": 1,
                "bbox": None,
            }
        ]

    def _parse_docx(self, content: bytes) -> list:
        """Parse DOCX file using python-docx."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx is required for DOCX parsing. Install with: pip install python-docx"
            )

        doc = Document(io.BytesIO(content))
        blocks = []

        # Extract paragraphs
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                # Detect heading level
                block_type = "text"
                if para.style.name.startswith("Heading"):
                    block_type = "header"

                blocks.append(
                    {
                        "type": block_type,
                        "content": text,
                        "page": 1,  # DOCX doesn't have page info without rendering
                        "bbox": None,
                        "style": para.style.name,
                    }
                )

        # Extract tables
        for table_idx, table in enumerate(doc.tables):
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(cells)

            if rows:
                # Convert to Markdown table format
                md_table = self._table_to_markdown(rows)
                blocks.append(
                    {
                        "type": "table",
                        "content": md_table,
                        "page": 1,
                        "bbox": None,
                        "table_index": table_idx,
                    }
                )

        return blocks

    def _parse_pptx(self, content: bytes) -> list:
        """Parse PPTX file using python-pptx."""
        try:
            from pptx import Presentation
            from pptx.util import Inches
        except ImportError:
            raise ImportError(
                "python-pptx is required for PPTX parsing. Install with: pip install python-pptx"
            )

        prs = Presentation(io.BytesIO(content))
        blocks = []

        for slide_num, slide in enumerate(prs.slides, 1):
            slide_texts = []

            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_texts.append(shape.text.strip())

                # Handle tables in slides
                if shape.has_table:
                    rows = []
                    for row in shape.table.rows:
                        cells = [cell.text.strip() for cell in row.cells]
                        rows.append(cells)
                    if rows:
                        md_table = self._table_to_markdown(rows)
                        blocks.append(
                            {
                                "type": "table",
                                "content": md_table,
                                "page": slide_num,
                                "bbox": None,
                            }
                        )

            # Combine slide text
            if slide_texts:
                blocks.append(
                    {
                        "type": "text",
                        "content": "\n".join(slide_texts),
                        "page": slide_num,
                        "bbox": None,
                    }
                )

        return blocks

    def _parse_text(self, content: bytes) -> list:
        """Parse plain text file."""
        text = content.decode("utf-8", errors="ignore")
        blocks = []
        paras = text.split("\n\n")
        for p in paras:
            if p.strip():
                blocks.append({"type": "text", "content": p.strip(), "page": 1, "bbox": None})
        return blocks

    def _table_to_markdown(self, rows: list) -> str:
        """Convert table rows to Markdown format."""
        if not rows:
            return ""

        lines = []
        for i, row in enumerate(rows):
            line = "| " + " | ".join(row) + " |"
            lines.append(line)
            if i == 0:
                # Add header separator
                sep = "| " + " | ".join(["---"] * len(row)) + " |"
                lines.append(sep)

        return "\n".join(lines)
