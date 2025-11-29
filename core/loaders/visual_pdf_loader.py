from typing import List, Optional, Tuple, Dict
from core.state import ProcessedChunk
import os


class ParsingRule:
    def __init__(
        self,
        prefer_ocr: bool = True,
        force_vision: bool = False,
        table_threshold: int = 1,
        text_length_threshold: int = 400,
        cache_enabled: bool = True,
        max_cache_entries: int = 16,
    ):
        self.prefer_ocr = prefer_ocr
        self.force_vision = force_vision
        self.table_threshold = table_threshold
        self.text_length_threshold = text_length_threshold
        self.cache_enabled = cache_enabled
        self.max_cache_entries = max_cache_entries


class VisualPDFLoader:
    def __init__(self, parsing_rule: Optional[ParsingRule] = None):
        self.parsing_rule = parsing_rule or ParsingRule()
        self._page_cache: Dict[str, List[Tuple[bytes, str]]] = {}
        self._table_cache: Dict[str, List[Tuple[bytes, Tuple[int, int, int, int]]]] = {}

    async def process_pdf(self, pdf_path: str) -> List[ProcessedChunk]:
        pages = await self._pdf_pages(pdf_path)
        chunks: List[ProcessedChunk] = []
        for page_index, (image_bytes, page_text) in enumerate(pages, start=1):
            table_crops = self._detect_tables_cached(pdf_path, page_index, image_bytes)
            for idx, (crop_bytes, bbox) in enumerate(table_crops):
                table_md = await self._extract_table_markdown(crop_bytes)
                if table_md:
                    for j, c in enumerate(self._chunk_text(table_md)):
                        chunks.append({
                            "id": f"{pdf_path}-p{page_index}-table-{idx}-chunk-{j}",
                            "content": c,
                            "page_num": page_index,
                            "doc_id": pdf_path,
                            "chunk_index": j,
                            "metadata": {"type": "table", "bbox": bbox, "confidence": 0.0},
                        })

            markdown = await self._extract_markdown(image_bytes, page_text, page_index, len(table_crops))
            for i, chunk in enumerate(self._chunk_text(markdown)):
                chunks.append({
                    "id": f"{pdf_path}-p{page_index}-chunk-{i}",
                    "content": chunk,
                    "page_num": page_index,
                    "doc_id": pdf_path,
                    "chunk_index": i,
                    "metadata": {"type": "visual", "confidence": 0.0},
                })
        return chunks

    async def _pdf_pages(self, pdf_path: str) -> List[Tuple[bytes, str]]:
        try:
            import fitz  # PyMuPDF
        except Exception:
            return []

        if self.parsing_rule.cache_enabled and pdf_path in self._page_cache:
            return self._page_cache[pdf_path]

        pages: List[Tuple[bytes, str]] = []
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(alpha=False, matrix=fitz.Matrix(2, 2))
            image_bytes = pix.tobytes("png")
            page_text = page.get_text("text") or ""
            pages.append((image_bytes, page_text))
        doc.close()
        if self.parsing_rule.cache_enabled:
            if len(self._page_cache) >= self.parsing_rule.max_cache_entries:
                self._page_cache.pop(next(iter(self._page_cache)))
            self._page_cache[pdf_path] = pages
        return pages

    async def _extract_markdown(self, image_bytes: bytes, page_text: str, page_index: int, table_count: int) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        use_vision = self._should_use_vision(page_text, table_count)
        if api_key and (not self.parsing_rule.prefer_ocr or self.parsing_rule.force_vision or use_vision):
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    "将此页面内容转换为结构化Markdown，保持标题层级、列表与表格结构。"
                    "若为表格，请尽可能准确还原，保留合并单元格信息。"
                )
                resp = model.generate_content([
                    {"role": "user", "parts": [
                        prompt,
                        {"mime_type": "image/png", "data": image_bytes},
                    ]}
                ])
                text = getattr(resp, "text", "").strip()
                if text:
                    return text
            except Exception:
                pass

        # Fallback：使用页面文本简易转Markdown
        md_lines: List[str] = [f"# Page {page_index}"]
        for line in (page_text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) < 80:
                md_lines.append(f"## {line}")
            else:
                md_lines.append(line)
        return "\n\n".join(md_lines)

    def _should_use_vision(self, page_text: str, table_count: int) -> bool:
        if self.parsing_rule.force_vision:
            return True
        if table_count >= self.parsing_rule.table_threshold:
            return True
        if len(page_text or "") < self.parsing_rule.text_length_threshold:
            return True
        return False

    def _detect_tables(self, image_bytes: bytes) -> List[Tuple[bytes, Tuple[int, int, int, int]]]:
        try:
            import cv2
            import numpy as np
        except Exception:
            return []

        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10)
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
        lines_h = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel_h)
        lines_v = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel_v)
        table_mask = cv2.add(lines_h, lines_v)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions: List[Tuple[bytes, Tuple[int, int, int, int]]] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h < 5000 or w < 50 or h < 50:
                continue
            crop = img[y : y + h, x : x + w]
            ok, enc = cv2.imencode(".png", crop)
            if not ok:
                continue
            regions.append((enc.tobytes(), (x, y, w, h)))
        regions.sort(key=lambda r: (r[1][1], r[1][0]))
        return regions

    def _detect_tables_cached(self, pdf_path: str, page_index: int, image_bytes: bytes) -> List[Tuple[bytes, Tuple[int, int, int, int]]]:
        cache_key = f"{pdf_path}#p{page_index}"
        if self.parsing_rule.cache_enabled and cache_key in self._table_cache:
            return self._table_cache[cache_key]
        regions = self._detect_tables(image_bytes)
        if self.parsing_rule.cache_enabled:
            if len(self._table_cache) >= self.parsing_rule.max_cache_entries:
                self._table_cache.pop(next(iter(self._table_cache)))
            self._table_cache[cache_key] = regions
        return regions

    async def _extract_table_markdown(self, crop_bytes: bytes) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and not self.parsing_rule.prefer_ocr:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    "将此表格图片转换为Markdown表格，确保数值精确，保留合并单元格结构。"
                )
                resp = model.generate_content([
                    {"role": "user", "parts": [
                        prompt,
                        {"mime_type": "image/png", "data": crop_bytes},
                    ]}
                ])
                text = getattr(resp, "text", "").strip()
                if text:
                    return text
            except Exception:
                pass
        return ""

    def _chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
        size = 1000
        return [text[i : i + size] for i in range(0, len(text), size)]
