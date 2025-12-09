"""
Comic Processor - Comic/Manga recognition and understanding.

Features:
- Panel detection (分格检测)
- Speech bubble OCR (气泡文字识别)
- Scene description using VLM
- Reading order detection (RTL for manga, LTR for western comics)
"""

import asyncio
import io
import logging
from typing import Any, Literal

from core.state import IngestState
from core.utils.monitor import ingest_duration

logger = logging.getLogger(__name__)


# Reading order types
ReadingOrder = Literal["rtl", "ltr"]


class Panel:
    """Represents a detected comic panel."""

    def __init__(
        self,
        bbox: list[float],
        page: int,
        order: int,
        panel_type: str = "normal",
        confidence: float = 0.0,
    ):
        self.bbox = bbox  # [x0, y0, x1, y1]
        self.page = page
        self.order = order
        self.panel_type = panel_type  # "normal", "splash", "bleed"
        self.confidence = confidence
        self.bubbles: list[SpeechBubble] = []
        self.scene_description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox,
            "page": self.page,
            "order": self.order,
            "panel_type": self.panel_type,
            "confidence": self.confidence,
            "bubbles": [b.to_dict() for b in self.bubbles],
            "scene_description": self.scene_description,
        }


class SpeechBubble:
    """Represents a detected speech bubble with text."""

    def __init__(
        self,
        bbox: list[float],
        text: str = "",
        bubble_type: str = "speech",
        speaker: str | None = None,
        confidence: float = 0.0,
    ):
        self.bbox = bbox
        self.text = text
        self.bubble_type = bubble_type  # "speech", "thought", "narration", "sfx"
        self.speaker = speaker
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox,
            "text": self.text,
            "bubble_type": self.bubble_type,
            "speaker": self.speaker,
            "confidence": self.confidence,
        }


class ComicProcessor:
    """
    Processes comic/manga images for knowledge base ingestion.

    This capability is part of the professional tier and supports:
    - JPG, PNG, PDF, CBZ, CBR formats
    - Panel (frame) detection
    - Speech bubble OCR
    - Scene description via VLM
    - Configurable reading order

    Configuration:
        panel_detection: bool - Detect comic panels
        bubble_ocr: bool - OCR text in speech bubbles
        scene_description: bool - Describe each panel with VLM
        reading_order: "rtl" | "ltr" - Reading direction
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.panel_detection = self.config.get("panel_detection", True)
        self.bubble_ocr = self.config.get("bubble_ocr", True)
        self.scene_description = self.config.get("scene_description", False)
        self.reading_order: ReadingOrder = self.config.get("reading_order", "ltr")
        self._semaphore = asyncio.Semaphore(2)

    async def __call__(self, state: IngestState) -> IngestState:
        """Process comic file from state."""
        with ingest_duration.labels(stage="comic_processor").time():
            return await self.process(state)

    async def process(self, state: IngestState) -> IngestState:
        """Process comic images and extract content."""
        file_type = state.get("file_type", "").lower()

        # Handle CBZ/CBR archives
        if file_type in ("cbz", "cbr"):
            images = await self._extract_from_archive(state)
            state["images"] = images
        else:
            images = state.get("images", [])

        if not images:
            logger.debug("No images to process as comic")
            return state

        all_panels: list[Panel] = []

        async with self._semaphore:
            for img in images:
                try:
                    panels = await self._process_page(img)
                    all_panels.extend(panels)
                except Exception as e:
                    logger.warning(f"Comic processing failed for page {img.get('page')}: {e}")
                    state["error_log"].append(
                        {
                            "stage": "comic_processor",
                            "error": str(e),
                            "page": img.get("page"),
                        }
                    )

        # Sort panels by reading order
        all_panels = self._sort_by_reading_order(all_panels)

        # Convert panels to parsed blocks
        parsed_blocks = self._panels_to_blocks(all_panels)
        state["parsed_blocks"] = parsed_blocks
        state["extracted_text"] = self._extract_text(all_panels)

        return state

    async def _extract_from_archive(self, state: IngestState) -> list[dict[str, Any]]:
        """Extract images from CBZ (zip) or CBR (rar) archives."""
        raw_content = state.get("raw_content")
        if not raw_content:
            file_path = state.get("file_path", "")
            from core.storage.blob_store import get_blob_store

            blob = get_blob_store()
            raw_content = await blob.get(file_path)

        file_type = state.get("file_type", "").lower()
        images = []

        try:
            if file_type == "cbz":
                # CBZ is just a ZIP file
                import zipfile

                with zipfile.ZipFile(io.BytesIO(raw_content)) as zf:
                    # Get image files sorted by name
                    image_files = sorted(
                        [
                            f
                            for f in zf.namelist()
                            if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                            and not f.startswith("__MACOSX")  # Skip macOS metadata
                        ]
                    )

                    for page_num, filename in enumerate(image_files):
                        image_data = zf.read(filename)
                        images.append(
                            {
                                "data": image_data,
                                "page": page_num,
                                "filename": filename,
                                "metadata": {"source": "cbz"},
                            }
                        )

            elif file_type == "cbr":
                # CBR requires rarfile library
                try:
                    import rarfile

                    with rarfile.RarFile(io.BytesIO(raw_content)) as rf:
                        image_files = sorted(
                            [
                                f
                                for f in rf.namelist()
                                if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
                            ]
                        )

                        for page_num, filename in enumerate(image_files):
                            image_data = rf.read(filename)
                            images.append(
                                {
                                    "data": image_data,
                                    "page": page_num,
                                    "filename": filename,
                                    "metadata": {"source": "cbr"},
                                }
                            )
                except ImportError:
                    logger.warning("rarfile not installed, cannot process CBR")

        except Exception as e:
            logger.error(f"Failed to extract from archive: {e}")

        logger.info(f"Extracted {len(images)} images from comic archive")
        return images

    async def _process_page(self, img: dict[str, Any]) -> list[Panel]:
        """Process a single comic page."""
        image_data = img.get("data")
        if not image_data:
            return []

        page_num = img.get("page", 0)
        panels = []

        # Step 1: Detect panels
        if self.panel_detection:
            panels = await self._detect_panels(image_data, page_num)
        else:
            # Treat entire page as single panel
            panels = [
                Panel(
                    bbox=await self._get_image_bounds(image_data),
                    page=page_num,
                    order=0,
                )
            ]

        # Step 2: OCR speech bubbles in each panel
        if self.bubble_ocr:
            for panel in panels:
                panel.bubbles = await self._detect_and_ocr_bubbles(image_data, panel.bbox)

        # Step 3: Generate scene descriptions
        if self.scene_description:
            for panel in panels:
                panel.scene_description = await self._describe_panel(image_data, panel.bbox)

        return panels

    async def _detect_panels(self, image_data: bytes, page: int) -> list[Panel]:
        """Detect comic panels using computer vision."""
        try:
            import cv2
            import numpy as np

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            height, width = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Edge detection for panel borders
            edges = cv2.Canny(gray, 50, 150)

            # Dilate to connect edge fragments
            kernel = np.ones((3, 3), np.uint8)
            dilated = cv2.dilate(edges, kernel, iterations=2)

            # Find contours
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            panels = []
            min_panel_area = (width * height) * 0.02  # Min 2% of page

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h

                if area < min_panel_area:
                    continue

                # Skip if too close to page edges (likely page border)
                if x < 5 and y < 5 and w > width * 0.95 and h > height * 0.95:
                    continue

                panels.append(
                    Panel(
                        bbox=[x, y, x + w, y + h],
                        page=page,
                        order=len(panels),
                        confidence=0.8,
                    )
                )

            # If no panels detected, treat whole page as one panel
            if not panels:
                panels.append(
                    Panel(
                        bbox=[0, 0, width, height],
                        page=page,
                        order=0,
                        panel_type="splash",
                        confidence=0.5,
                    )
                )

            # Sort panels by reading order (initial sort, will be refined)
            panels = self._sort_panels_on_page(panels)

            logger.debug(f"Detected {len(panels)} panels on page {page}")
            return panels

        except ImportError:
            logger.warning("OpenCV not installed, treating page as single panel")
            return [
                Panel(
                    bbox=[0, 0, 1000, 1000],  # Placeholder
                    page=page,
                    order=0,
                )
            ]
        except Exception as e:
            logger.error(f"Panel detection failed: {e}")
            return []

    def _sort_panels_on_page(self, panels: list[Panel]) -> list[Panel]:
        """Sort panels on a single page according to reading order."""
        if not panels:
            return panels

        # Group panels into rows (similar y-coordinate)
        rows: list[list[Panel]] = []
        sorted_by_y = sorted(panels, key=lambda p: p.bbox[1])

        current_row: list[Panel] = []
        current_y = sorted_by_y[0].bbox[1]
        row_threshold = 50  # pixels

        for panel in sorted_by_y:
            if abs(panel.bbox[1] - current_y) <= row_threshold:
                current_row.append(panel)
            else:
                if current_row:
                    rows.append(current_row)
                current_row = [panel]
                current_y = panel.bbox[1]

        if current_row:
            rows.append(current_row)

        # Sort panels within each row
        sorted_panels = []
        for row in rows:
            if self.reading_order == "rtl":
                # Right to left (manga)
                row_sorted = sorted(row, key=lambda p: -p.bbox[0])
            else:
                # Left to right (western)
                row_sorted = sorted(row, key=lambda p: p.bbox[0])
            sorted_panels.extend(row_sorted)

        # Update order index
        for idx, panel in enumerate(sorted_panels):
            panel.order = idx

        return sorted_panels

    async def _detect_and_ocr_bubbles(
        self, image_data: bytes, panel_bbox: list[float]
    ) -> list[SpeechBubble]:
        """Detect and OCR speech bubbles within a panel area."""
        try:
            import cv2
            import numpy as np

            # Decode and crop to panel
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            x0, y0, x1, y1 = (int(v) for v in panel_bbox)
            panel_img = img[y0:y1, x0:x1]

            # Convert to grayscale
            gray = cv2.cvtColor(panel_img, cv2.COLOR_BGR2GRAY)

            # Threshold to find white bubbles
            _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

            # Find contours (bubbles are typically white/light colored)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            bubbles = []
            min_bubble_area = 500  # Minimum pixels

            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h

                if area < min_bubble_area:
                    continue

                # Check if roughly circular/oval (bubble-like)
                aspect_ratio = w / h if h > 0 else 0
                if aspect_ratio < 0.3 or aspect_ratio > 3:
                    continue

                # OCR the bubble region
                bubble_img = panel_img[y : y + h, x : x + w]
                text = await self._ocr_region(bubble_img)

                if text.strip():  # Only add if text found
                    bubbles.append(
                        SpeechBubble(
                            bbox=[x0 + x, y0 + y, x0 + x + w, y0 + y + h],
                            text=text,
                            bubble_type=self._classify_bubble(text),
                            confidence=0.7,
                        )
                    )

            logger.debug(f"Detected {len(bubbles)} speech bubbles")
            return bubbles

        except ImportError:
            return []
        except Exception as e:
            logger.warning(f"Bubble detection failed: {e}")
            return []

    async def _ocr_region(self, region_img) -> str:
        """OCR a specific image region."""
        try:
            import numpy as np
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="ch+en", show_log=False)
            result = ocr.ocr(region_img, cls=True)

            if not result or not result[0]:
                return ""

            texts = []
            for line in result[0]:
                _, (text, _) = line
                texts.append(text)

            return " ".join(texts)

        except ImportError:
            logger.warning("PaddleOCR not installed")
            return ""
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def _classify_bubble(self, text: str) -> str:
        """Classify bubble type based on content heuristics."""
        text_lower = text.lower()

        # Sound effects are typically short and use special characters
        if len(text) < 5 and any(c in text for c in "!*#@"):
            return "sfx"

        # Narration boxes often start with time/location indicators
        if any(text_lower.startswith(w) for w in ["meanwhile", "later", "在", "其后", "时间"]):
            return "narration"

        # Default to speech
        return "speech"

    async def _describe_panel(self, image_data: bytes, panel_bbox: list[float]) -> str:
        """Generate a scene description for a panel using VLM."""
        try:
            import cv2
            import numpy as np

            # Crop to panel
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return ""

            x0, y0, x1, y1 = (int(v) for v in panel_bbox)
            panel_img = img[y0:y1, x0:x1]

            # Encode as JPEG
            _, buffer = cv2.imencode(".jpg", panel_img)
            panel_data = buffer.tobytes()

            # Use ImageCaptioner
            from core.ingestion.nodes.image_captioner import ImageCaptioner

            captioner = ImageCaptioner()
            temp_state = {
                "images": [{"data": panel_data, "page": 0}],
                "parsed_blocks": [],
                "strategy_config": {"vlm_provider": "auto"},
                "error_log": [],
            }

            result = await captioner(temp_state)
            blocks = result.get("parsed_blocks", [])

            if blocks:
                return blocks[0].get("content", "")

            return ""

        except Exception as e:
            logger.warning(f"Panel description failed: {e}")
            return ""

    async def _get_image_bounds(self, image_data: bytes) -> list[float]:
        """Get image dimensions as bounding box."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            return [0, 0, img.width, img.height]
        except Exception:
            return [0, 0, 1000, 1000]

    def _sort_by_reading_order(self, panels: list[Panel]) -> list[Panel]:
        """Sort all panels by page and reading order."""
        return sorted(panels, key=lambda p: (p.page, p.order))

    def _panels_to_blocks(self, panels: list[Panel]) -> list[dict[str, Any]]:
        """Convert panels to parsed blocks for ingestion."""
        blocks = []

        for panel in panels:
            # Create a block for the panel
            content_parts = []

            # Add scene description if available
            if panel.scene_description:
                content_parts.append(f"[Scene: {panel.scene_description}]")

            # Add speech bubble texts
            for bubble in panel.bubbles:
                bubble_prefix = {
                    "speech": "💬",
                    "thought": "💭",
                    "narration": "📖",
                    "sfx": "💥",
                }.get(bubble.bubble_type, "💬")

                if bubble.speaker:
                    content_parts.append(f"{bubble_prefix} {bubble.speaker}: {bubble.text}")
                else:
                    content_parts.append(f"{bubble_prefix} {bubble.text}")

            if content_parts:
                blocks.append(
                    {
                        "type": "text",
                        "content": "\n".join(content_parts),
                        "page": panel.page,
                        "bbox": panel.bbox,
                        "metadata": {
                            "block_type": "comic_panel",
                            "panel_order": panel.order,
                            "panel_type": panel.panel_type,
                            "bubble_count": len(panel.bubbles),
                            "has_description": bool(panel.scene_description),
                        },
                    }
                )

        return blocks

    def _extract_text(self, panels: list[Panel]) -> str:
        """Extract plain text from all panels."""
        texts = []

        for panel in panels:
            panel_texts = []

            if panel.scene_description:
                panel_texts.append(f"[{panel.scene_description}]")

            for bubble in panel.bubbles:
                panel_texts.append(bubble.text)

            if panel_texts:
                texts.append(
                    f"Page {panel.page + 1}, Panel {panel.order + 1}:\n" + "\n".join(panel_texts)
                )

        return "\n\n".join(texts)


# Factory function for capability loading
def create_comic_processor(config: dict[str, Any] | None = None) -> ComicProcessor:
    """Factory function for creating ComicProcessor instances."""
    return ComicProcessor(config)
