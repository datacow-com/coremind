from core.state import ProcessedChunk


class ParsingRule:
    def __init__(
        self,
        prefer_ocr: bool = True,
        force_vision: bool = False,
        table_threshold: int = 1,
        text_length_threshold: int = 400,
        short_line_ratio_threshold: float = 0.6,
        punct_ratio_threshold: float = 0.15,
        cache_enabled: bool = True,
        max_cache_entries: int = 16,
        semantic: bool = False,
        denoise: bool = False,
    ):
        self.prefer_ocr = prefer_ocr
        self.force_vision = force_vision
        self.table_threshold = table_threshold
        self.text_length_threshold = text_length_threshold
        self.short_line_ratio_threshold = short_line_ratio_threshold
        self.punct_ratio_threshold = punct_ratio_threshold
        self.cache_enabled = cache_enabled
        self.max_cache_entries = max_cache_entries
        self.semantic = semantic
        self.denoise = denoise


class VisualPDFLoader:
    def __init__(self, parsing_rule: ParsingRule | None = None):
        self.parsing_rule = parsing_rule or ParsingRule()
        self._page_cache: dict[str, list[tuple[bytes, str]]] = {}
        self._table_cache: dict[str, list[tuple[bytes, tuple[int, int, int, int]]]] = {}
        self._block_cache: dict[str, list[tuple[str, tuple[int, int, int, int]]]] = {}

    async def process_pdf(self, pdf_path: str) -> list[ProcessedChunk]:
        pages = await self._pdf_pages(pdf_path)
        chunks: list[ProcessedChunk] = []
        for page_index, (image_bytes, page_text) in enumerate(pages, start=1):
            try:
                from io import BytesIO

                from PIL import Image

                im = Image.open(BytesIO(image_bytes))
                w, h = im.size
            except Exception:
                w, h = (0, 0)
            table_crops = self._detect_tables_cached(pdf_path, page_index, image_bytes)
            for idx, (crop_bytes, bbox) in enumerate(table_crops):
                table_md = await self._extract_table_markdown(crop_bytes)
                if table_md:
                    for j, c in enumerate(self._chunk_text(table_md)):
                        chunks.append(
                            {
                                "id": f"{pdf_path}-p{page_index}-table-{idx}-chunk-{j}",
                                "content": c,
                                "page_num": page_index,
                                "doc_id": pdf_path,
                                "chunk_index": j,
                                "metadata": {
                                    "block_type": "table",
                                    "bbox": bbox,
                                    "confidence": 0.0,
                                    "table_id": idx,
                                    "heading_level": None,
                                },
                            }
                        )

            markdown = await self._extract_markdown(
                image_bytes, page_text, page_index, len(table_crops)
            )
            used_vision = (
                (not self.parsing_rule.prefer_ocr)
                or self.parsing_rule.force_vision
                or self._should_use_vision(page_text, len(table_crops))
            )
            if used_vision:
                for i, chunk in enumerate(self._chunk_text(markdown)):
                    parent_id = None
                    if getattr(self.parsing_rule, "semantic", False):
                        import re

                        m = re.search(r"^(#{1,6}\s*(.+))$", chunk, re.MULTILINE)
                        if m:
                            title = m.group(2).strip()
                            if title:
                                parent_id = f"{pdf_path}-p{page_index}-parent-{abs(hash(title))}"
                    import re

                    hm = re.match(r"^(#{1,6})\s", chunk)
                    hlevel = len(hm.group(1)) if hm else None
                    chunks.append(
                        {
                            "id": f"{pdf_path}-p{page_index}-chunk-{i}",
                            "content": chunk,
                            "page_num": page_index,
                            "doc_id": pdf_path,
                            "chunk_index": i,
                            "metadata": {
                                "block_type": "heading" if hlevel else "paragraph",
                                "confidence": 0.0,
                                "bbox": (0, 0, w, h),
                                "parent_id": parent_id,
                                "heading_level": hlevel,
                                "table_id": None,
                            },
                        }
                    )
            else:
                cache_key = f"{pdf_path}#p{page_index}"
                blocks = self._block_cache.get(cache_key, [])
                if not blocks:
                    for i, chunk in enumerate(self._chunk_text(markdown)):
                        parent_id = None
                        if getattr(self.parsing_rule, "semantic", False):
                            import re

                            m = re.search(r"^(#{1,6}\s*(.+))$", chunk, re.MULTILINE)
                            if m:
                                title = m.group(2).strip()
                                if title:
                                    parent_id = (
                                        f"{pdf_path}-p{page_index}-parent-{abs(hash(title))}"
                                    )
                        import re

                        hm = re.match(r"^(#{1,6})\s", chunk)
                        hlevel = len(hm.group(1)) if hm else None
                        chunks.append(
                            {
                                "id": f"{pdf_path}-p{page_index}-chunk-{i}",
                                "content": chunk,
                                "page_num": page_index,
                                "doc_id": pdf_path,
                                "chunk_index": i,
                                "metadata": {
                                    "block_type": "heading" if hlevel else "paragraph",
                                    "confidence": 0.0,
                                    "bbox": (0, 0, w, h),
                                    "parent_id": parent_id,
                                    "heading_level": hlevel,
                                    "table_id": None,
                                },
                            }
                        )
                else:
                    for bi, (btxt, bbbox) in enumerate(blocks):
                        line = btxt.strip()
                        if not line:
                            continue
                        content = f"## {line}" if len(line) < 80 else line
                        parent_id = None
                        if getattr(self.parsing_rule, "semantic", False):
                            parent_id = f"{pdf_path}-p{page_index}-parent-{abs(hash(line))}"
                        chunks.append(
                            {
                                "id": f"{pdf_path}-p{page_index}-block-{bi}",
                                "content": content,
                                "page_num": page_index,
                                "doc_id": pdf_path,
                                "chunk_index": bi,
                                "metadata": {
                                    "block_type": "heading"
                                    if content.startswith("## ")
                                    else "paragraph",
                                    "confidence": 0.0,
                                    "bbox": bbbox,
                                    "parent_id": parent_id,
                                    "heading_level": 2 if content.startswith("## ") else None,
                                    "table_id": None,
                                },
                            }
                        )
        return chunks

    async def _pdf_pages(self, pdf_path: str) -> list[tuple[bytes, str]]:
        try:
            import fitz  # PyMuPDF
        except Exception:
            return []

        if self.parsing_rule.cache_enabled and pdf_path in self._page_cache:
            return self._page_cache[pdf_path]

        pages: list[tuple[bytes, str]] = []
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(alpha=False, matrix=fitz.Matrix(2, 2))
            image_bytes = pix.tobytes("png")
            page_text = page.get_text("text") or ""
            pages.append((image_bytes, page_text))
            try:
                cache_key = f"{pdf_path}#p{i}"
                blist: list[tuple[str, tuple[int, int, int, int]]] = []
                blocks = page.get_text("blocks") or []
                for b in blocks:
                    if isinstance(b, (list, tuple)) and len(b) >= 5:
                        x0, y0, x1, y1 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
                        txt = str(b[4] or "").strip()
                        if txt:
                            blist.append((txt, (x0, y0, x1 - x0, y1 - y0)))
                try:
                    from core.vision.layout_analyzer import analyze_blocks

                    la_boxes = analyze_blocks(image_bytes)
                    la_list = [("", (x, y, w, h)) for (x, y, w, h) in la_boxes]
                except Exception:
                    la_list = []
                try:
                    import os as _os

                    from core.vision.yolo_detector import detect_blocks_yolo

                    yolo_enabled = bool(_os.environ.get("YOLO_ENABLED"))
                    model_path = _os.environ.get("YOLO_MODEL")
                    yo_list = []
                    if yolo_enabled and model_path:
                        yo_boxes = detect_blocks_yolo(image_bytes, model_path)
                        yo_list = [("", (x, y, w, h)) for (x, y, w, h) in yo_boxes]
                except Exception:
                    yo_list = []
                # fuse blocks: PyMuPDF blocks + layout analyzer + YOLO (unique by bbox)
                all_blocks = blist + la_list + yo_list
                uniq: list[tuple[str, tuple[int, int, int, int]]] = []
                seen = set()
                for txt, bb in all_blocks:
                    key = (bb[0], bb[1], bb[2], bb[3])
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append((txt, bb))
                blist = uniq
                try:
                    import os as _os

                    from core.vision.layoutlm_parser import classify_blocks_layoutlm

                    clf_name = _os.environ.get("LAYOUTLM_CLASS_MODEL")
                    if clf_name and blist:
                        boxes = [bb for _, bb in blist]
                        cls = classify_blocks_layoutlm(image_bytes, boxes, clf_name)
                        tmp = []
                        for (txt, bb), lab in zip(blist, cls, strict=False):
                            labn = (
                                lab if lab in {"paragraph", "heading", "table", "figure"} else txt
                            )
                            tmp.append((labn, bb))
                        blist = tmp
                except Exception:
                    pass
                self._block_cache[cache_key] = blist
            except Exception:
                pass
        doc.close()
        if self.parsing_rule.cache_enabled:
            if len(self._page_cache) >= self.parsing_rule.max_cache_entries:
                self._page_cache.pop(next(iter(self._page_cache)))
            self._page_cache[pdf_path] = pages
        return pages

    async def _extract_markdown(
        self, image_bytes: bytes, page_text: str, page_index: int, table_count: int
    ) -> str:
        use_vision = self._should_use_vision(page_text, table_count)
        if not self.parsing_rule.prefer_ocr or self.parsing_rule.force_vision or use_vision:
            try:
                from core.llm.gateway import LLMGateway
                from server.config import settings

                gw = LLMGateway(provider=settings.vision_provider or "dashscope")
                prompt = (
                    "将此页面内容转换为结构化Markdown，保持标题层级、列表与表格结构。"
                    "若为表格，请尽可能准确还原，保留合并单元格信息。"
                )
                text = await gw.vision_markdown(image_bytes=image_bytes, prompt=prompt)
                if text:
                    return text
            except Exception:
                pass

        # Fallback：使用页面文本简易转Markdown
        md_lines: list[str] = [f"# Page {page_index}"]
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
        score = self._complexity_score(page_text or "", table_count)
        return score >= 1.0

    def _complexity_score(self, txt: str, table_count: int) -> float:
        if table_count >= self.parsing_rule.table_threshold:
            return 1.2
        if not txt:
            return 1.0
        lines = [line.strip() for line in txt.splitlines() if line.strip()]
        short_lines = [line for line in lines if len(line) < 80]
        short_ratio = (len(short_lines) / max(len(lines), 1)) if lines else 1.0
        puncts = sum([1 for ch in txt if ch in ",.;:!?"])
        punct_ratio = (puncts / max(len(txt), 1)) if txt else 0.0
        base = 0.0
        if len(txt) < self.parsing_rule.text_length_threshold:
            base += 0.6
        if short_ratio >= self.parsing_rule.short_line_ratio_threshold:
            base += 0.4
        if punct_ratio <= self.parsing_rule.punct_ratio_threshold:
            base += 0.3
        return base

    def _detect_tables(self, image_bytes: bytes) -> list[tuple[bytes, tuple[int, int, int, int]]]:
        try:
            import cv2
            import numpy as np
        except Exception:
            return []

        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            return []
        if getattr(self.parsing_rule, "denoise", False):
            img = self._preprocess_image(img)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thr = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
        )
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))
        lines_h = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel_h)
        lines_v = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel_v)
        table_mask = cv2.add(lines_h, lines_v)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions: list[tuple[bytes, tuple[int, int, int, int]]] = []
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

    def _preprocess_image(self, img):
        try:
            import cv2
        except Exception:
            return img
        den = cv2.bilateralFilter(img, 7, 75, 75)
        kern = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        opn = cv2.morphologyEx(den, cv2.MORPH_OPEN, kern)
        return opn

    def _detect_tables_cached(
        self, pdf_path: str, page_index: int, image_bytes: bytes
    ) -> list[tuple[bytes, tuple[int, int, int, int]]]:
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
        if not self.parsing_rule.prefer_ocr:
            try:
                from core.llm.gateway import LLMGateway
                from server.config import settings

                gw = LLMGateway(provider=settings.vision_provider or "dashscope")
                text = await gw.vision_table_markdown(image_bytes=crop_bytes)
                if text:
                    return text
            except Exception:
                pass
        return ""

    def _chunk_text(self, text: str) -> list[str]:
        if not text:
            return []
        if getattr(self.parsing_rule, "semantic", False):
            return self._chunk_text_semantic(text)
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        buf: list[str] = []
        target_min, target_max = 800, 1400
        for p in paras:
            if len("\n\n".join(buf)) < target_min:
                buf.append(p)
                if len("\n\n".join(buf)) >= target_min:
                    chunks.append("\n\n".join(buf))
                    buf = []
            else:
                chunks.append("\n\n".join(buf))
                buf = [p]
        if buf:
            chunks.append("\n\n".join(buf))
        # 如果单个chunk过长，进行二次切分
        out: list[str] = []
        for c in chunks:
            if len(c) <= target_max:
                out.append(c)
            else:
                for i in range(0, len(c), target_max):
                    out.append(c[i : i + target_max])
        return out

    def _chunk_text_semantic(self, text: str) -> list[str]:
        import re

        heads = list(re.finditer(r"^(#{1,6}[^\n]+)$", text, re.MULTILINE))
        if not heads:
            return self._chunk_text(text)
        parts: list[str] = []
        for i, h in enumerate(heads):
            start = h.start()
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            seg = text[start:end].strip()
            if seg:
                parts.append(seg)
        out: list[str] = []
        target_max = 1400
        for p in parts:
            if len(p) <= target_max:
                out.append(p)
            else:
                for i in range(0, len(p), target_max):
                    out.append(p[i : i + target_max])
        return out
