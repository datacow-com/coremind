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
    """
    try:
        import cv2
        import numpy as np
        from ultralytics import YOLO
    except Exception:
        return []
    if not model_path:
        return []
    try:
        model = YOLO(model_path)
    except Exception:
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
