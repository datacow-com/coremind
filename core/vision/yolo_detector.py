def detect_blocks_yolo(
    image_bytes: bytes, model_path: str | None = None
) -> list[tuple[int, int, int, int]]:
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
        res = model.predict(img, conf=0.25, iou=0.4, verbose=False)
        boxes: list[tuple[int, int, int, int]] = []
        for r in res:
            for b in getattr(r, "boxes", []):
                xyxy = b.xyxy[0].tolist()  # [x1,y1,x2,y2]
                x1, y1, x2, y2 = (int(v) for v in xyxy)
                w, h = max(0, x2 - x1), max(0, y2 - y1)
                if w * h < 2000 or w < 30 or h < 30:
                    continue
                boxes.append((x1, y1, w, h))
        boxes.sort(key=lambda bb: (bb[1], bb[0]))
        return boxes
    except Exception:
        return []
