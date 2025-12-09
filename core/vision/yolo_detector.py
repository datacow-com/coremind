"""
YOLO Block Detector with Singleton Pattern.
Loads the model once and reuses it across all requests.
"""

import threading
from functools import lru_cache

# Singleton cache for YOLO models
_YOLO_CACHE: dict[str, object] = {}  # model_path -> YOLO instance
_YOLO_LOCK = threading.Lock()


@lru_cache(maxsize=4)
def _get_yolo_model(model_path: str):
    """Load and cache YOLO model. LRU cache ensures we keep up to 4 models."""
    try:
        from ultralytics import YOLO

        return YOLO(model_path)
    except Exception:
        return None


def detect_blocks_yolo(
    image_bytes: bytes,
    model_path: str | None = None,
    conf: float = 0.25,
    iou: float = 0.4,
    min_area: int = 2000,
    min_side: int = 30,
) -> list[tuple[int, int, int, int]]:
    """
    YOLO 版面/块检测，需传入模型路径；失败返回空列表。

    Performance Optimization:
    - Model is loaded only once per model_path via LRU cache
    - Subsequent calls reuse the cached model
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return []

    if not model_path:
        return []

    # Get cached model
    model = _get_yolo_model(model_path)
    if model is None:
        return []

    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        return []

    try:
        res = model.predict(img, conf=conf, iou=iou, verbose=False)
        boxes: list[tuple[int, int, int, int]] = []
        for r in res:
            for b in getattr(r, "boxes", []):
                xyxy = b.xyxy[0].tolist()  # [x1,y1,x2,y2]
                x1, y1, x2, y2 = (int(v) for v in xyxy)
                w, h = max(0, x2 - x1), max(0, y2 - y1)
                if w * h < min_area or w < min_side or h < min_side:
                    continue
                boxes.append((x1, y1, w, h))
        boxes.sort(key=lambda bb: (bb[1], bb[0]))
        return boxes
    except Exception:
        return []


def clear_yolo_cache():
    """Clear the YOLO model cache. Useful for memory management."""
    _get_yolo_model.cache_clear()
