"""
Layout Analyzer - Complex document layout structure recognition.

Features:
- Region detection (text, title, table, figure, header, footer)
- Reading order detection
- Multi-column layout handling
- Support for multiple layout analysis models
"""

import asyncio
import io
import logging
from typing import Any, Literal

try:
    from core.state import IngestState
    from core.utils.monitor import ingest_duration
except ImportError:
    IngestState = dict  # For standalone usage
    ingest_duration = None

logger = logging.getLogger(__name__)


# Legacy function - kept for backward compatibility
def analyze_blocks(
    image_bytes: bytes, min_area: int = 2000, min_side: int = 30
) -> list[tuple[int, int, int, int]]:
    """
    OpenCV 版面粗分割，带最小尺寸过滤；失败返回空列表。
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return []

    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    thr = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    morph = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h < min_area or w < min_side or h < min_side:
            continue
        boxes.append((x, y, w, h))
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes


# Layout element types
LayoutType = Literal[
    "title",
    "text",
    "table",
    "figure",
    "list",
    "header",
    "footer",
    "caption",
    "equation",
    "page_number",
]


class LayoutElement:
    """Represents a detected layout element."""

    def __init__(
        self,
        element_type: LayoutType,
        bbox: list[float],
        confidence: float,
        page: int,
        content: str | None = None,
        order: int | None = None,
    ):
        self.type = element_type
        self.bbox = bbox  # [x0, y0, x1, y1]
        self.confidence = confidence
        self.page = page
        self.content = content
        self.order = order  # Reading order

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "page": self.page,
            "content": self.content,
            "order": self.order,
        }


class LayoutAnalyzer:
    """
    Analyzes complex document layouts for better understanding.

    This capability is part of the professional tier and supports:
    - Multi-column document handling
    - Complex layout structure recognition
    - Reading order detection
    - Region classification

    Configuration:
        model: "yolo_doclayout" | "layoutlmv3" | "dit" | "pp_structure"
        detect_reading_order: bool - Identify correct reading order
    """

    # Model configurations
    MODEL_CONFIGS = {
        "yolo_doclayout": {
            "description": "YOLO-DocLayout (Fast, good for general layouts)",
            "input_size": 1280,
            "labels": ["text", "title", "figure", "table", "list", "equation"],
        },
        "layoutlmv3": {
            "description": "LayoutLMv3 (Precise, best for scanned docs)",
            "input_size": 1024,
            "labels": ["text", "title", "list", "table", "figure", "caption"],
        },
        "dit": {
            "description": "DiT (High precision for academic papers)",
            "input_size": 1024,
            "labels": ["text", "title", "figure", "table", "caption", "equation"],
        },
        "pp_structure": {
            "description": "PP-Structure (Optimized for Chinese documents)",
            "input_size": 960,
            "labels": ["text", "title", "figure", "table", "header", "footer"],
        },
    }

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.model_name = self.config.get("model", "pp_structure")
        self.detect_reading_order = self.config.get("detect_reading_order", True)
        self._model = None
        self._semaphore = asyncio.Semaphore(2)

    async def __call__(self, state: IngestState) -> IngestState:
        """Analyze layout of document pages."""
        if ingest_duration:
            with ingest_duration.labels(stage="layout_analyzer").time():
                return await self.analyze(state)
        return await self.analyze(state)

    async def analyze(self, state: IngestState) -> IngestState:
        """Analyze document layout and enhance parsed blocks."""
        images = state.get("images", [])

        if not images:
            logger.debug("No images to analyze for layout")
            return state

        all_elements = []

        for img in images:
            try:
                elements = await self._analyze_page(img)
                all_elements.extend(elements)
            except Exception as e:
                logger.warning(f"Layout analysis failed for page {img.get('page')}: {e}")
                if "error_log" in state:
                    state["error_log"].append(
                        {
                            "stage": "layout_analyzer",
                            "error": str(e),
                            "page": img.get("page"),
                        }
                    )

        # Sort by reading order if detected
        if self.detect_reading_order:
            all_elements = self._sort_by_reading_order(all_elements)

        # Convert elements to parsed blocks
        parsed_blocks = state.get("parsed_blocks", [])

        for elem in all_elements:
            block = {
                "type": self._map_layout_type(elem.type),
                "content": elem.content or "",
                "page": elem.page,
                "bbox": elem.bbox,
                "metadata": {
                    "layout_type": elem.type,
                    "confidence": elem.confidence,
                    "reading_order": elem.order,
                    "model": self.model_name,
                },
            }
            parsed_blocks.append(block)

        state["parsed_blocks"] = parsed_blocks
        return state

    async def _analyze_page(self, img: dict[str, Any]) -> list[LayoutElement]:
        """Analyze a single page image."""
        async with self._semaphore:
            image_data = img.get("data")
            if not image_data:
                return []

            page_num = img.get("page", 0)

            # Choose model
            if self.model_name == "pp_structure":
                return await self._analyze_with_pp_structure(image_data, page_num)
            elif self.model_name == "opencv":
                return await self._analyze_with_opencv(image_data, page_num)
            else:
                # Default to OpenCV-based detection for speed
                return await self._analyze_with_opencv(image_data, page_num)

    async def _analyze_with_pp_structure(self, image_data: bytes, page: int) -> list[LayoutElement]:
        """Analyze layout using PaddleOCR's PP-Structure."""
        try:
            import numpy as np
            from paddleocr import PPStructure
            from PIL import Image

            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            image_np = np.array(image)

            engine = PPStructure(show_log=False, layout=True)
            result = engine(image_np)

            elements = []
            for idx, item in enumerate(result):
                elem_type = item.get("type", "text").lower()
                bbox = item.get("bbox", [0, 0, 0, 0])

                elements.append(
                    LayoutElement(
                        element_type=self._normalize_type(elem_type),
                        bbox=bbox,
                        confidence=item.get("score", 0.9),
                        page=page,
                        content=item.get("res", {}).get("text", "")
                        if isinstance(item.get("res"), dict)
                        else "",
                        order=idx,
                    )
                )

            if self.detect_reading_order:
                elements = self._detect_reading_order_impl(elements)

            return elements

        except ImportError:
            logger.warning("PaddleOCR not installed, using OpenCV fallback")
            return await self._analyze_with_opencv(image_data, page)
        except Exception as e:
            logger.error(f"PP-Structure analysis failed: {e}")
            return await self._analyze_with_opencv(image_data, page)

    async def _analyze_with_opencv(self, image_data: bytes, page: int) -> list[LayoutElement]:
        """Analyze layout using OpenCV-based detection."""
        boxes = analyze_blocks(image_data)

        elements = []
        for idx, (x, y, w, h) in enumerate(boxes):
            # Simple heuristic classification based on dimensions
            aspect_ratio = w / h if h > 0 else 1

            if h < 50:  # Likely header/title
                elem_type = "title"
            elif aspect_ratio > 3:  # Wide - likely header/title
                elem_type = "title"
            elif aspect_ratio < 0.5:  # Tall - might be column
                elem_type = "text"
            else:
                elem_type = "text"

            elements.append(
                LayoutElement(
                    element_type=elem_type,
                    bbox=[x, y, x + w, y + h],
                    confidence=0.7,
                    page=page,
                    order=idx,
                )
            )

        return elements

    def _normalize_type(self, raw_type: str) -> LayoutType:
        """Normalize layout type label to standard type."""
        raw = raw_type.lower().strip()

        type_mapping = {
            "text": "text",
            "paragraph": "text",
            "title": "title",
            "heading": "title",
            "table": "table",
            "figure": "figure",
            "image": "figure",
            "list": "list",
            "header": "header",
            "footer": "footer",
            "caption": "caption",
            "equation": "equation",
            "page_number": "page_number",
        }

        return type_mapping.get(raw, "text")

    def _map_layout_type(self, layout_type: LayoutType) -> str:
        """Map layout type to standard block type."""
        mapping = {
            "title": "header",
            "text": "text",
            "table": "table",
            "figure": "image",
            "list": "text",
            "header": "header",
            "footer": "footer",
            "caption": "text",
            "equation": "text",
            "page_number": "metadata",
        }
        return mapping.get(layout_type, "text")

    def _detect_reading_order_impl(self, elements: list[LayoutElement]) -> list[LayoutElement]:
        """Detect and assign reading order to elements."""
        if not elements:
            return elements

        def sort_key(elem: LayoutElement) -> tuple[float, float]:
            y_center = (elem.bbox[1] + elem.bbox[3]) / 2
            x_center = (elem.bbox[0] + elem.bbox[2]) / 2
            y_bin = y_center // 50
            return (y_bin, x_center)

        sorted_elements = sorted(elements, key=sort_key)

        for idx, elem in enumerate(sorted_elements):
            elem.order = idx

        return sorted_elements

    def _sort_by_reading_order(self, elements: list[LayoutElement]) -> list[LayoutElement]:
        """Sort elements by their reading order."""
        return sorted(elements, key=lambda e: (e.page, e.order or 0))


# Factory function for capability loading
def create_layout_analyzer(config: dict[str, Any] | None = None) -> LayoutAnalyzer:
    """Factory function for creating LayoutAnalyzer instances."""
    return LayoutAnalyzer(config)
