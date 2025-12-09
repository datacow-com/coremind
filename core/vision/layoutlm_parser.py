"""
LayoutLMv3 Block Classifier with Singleton Pattern.
Loads the model once and reuses it across all requests.
"""

import threading
from functools import lru_cache

# Singleton cache for LayoutLM models
_LAYOUTLM_CACHE: dict[str, tuple] = {}  # model_name -> (processor, model)
_LAYOUTLM_LOCK = threading.Lock()


@lru_cache(maxsize=4)
def _get_layoutlm_model(model_name: str):
    """Load and cache LayoutLMv3 model. LRU cache ensures we keep up to 4 models."""
    try:
        from transformers import LayoutLMv3ForSequenceClassification, LayoutLMv3Processor

        processor = LayoutLMv3Processor.from_pretrained(model_name)
        model = LayoutLMv3ForSequenceClassification.from_pretrained(model_name)
        model.eval()  # Set to evaluation mode
        return processor, model
    except Exception:
        return None, None


def classify_blocks_layoutlm(
    image_bytes: bytes, boxes: list[tuple[int, int, int, int]], model_name: str | None
) -> list[str]:
    """
    LayoutLMv3 区块分类：传入模型名称；失败返回空标签。

    Performance Optimization:
    - Model is loaded only once per model_name via LRU cache
    - Subsequent calls reuse the cached model
    """
    if not model_name:
        return ["" for _ in boxes]

    try:
        from io import BytesIO

        import torch
        from PIL import Image
    except Exception:
        return ["" for _ in boxes]

    # Get cached model
    processor, model = _get_layoutlm_model(model_name)
    if processor is None or model is None:
        return ["" for _ in boxes]

    try:
        base = Image.open(BytesIO(image_bytes)).convert("RGB")
        labels: list[str] = []

        for x, y, w, h in boxes:
            try:
                crop = base.crop((x, y, x + w, y + h))
                inputs = processor(images=crop, return_tensors="pt")
                with torch.no_grad():
                    logits = model(**inputs).logits
                    pred = int(logits.argmax(dim=-1).item())
                id2label = getattr(model.config, "id2label", {})
                lbl = str(id2label.get(pred) or "")
                labels.append(lbl.lower())
            except Exception:
                labels.append("")

        return labels
    except Exception:
        return ["" for _ in boxes]


def clear_layoutlm_cache():
    """Clear the LayoutLM model cache. Useful for memory management."""
    _get_layoutlm_model.cache_clear()
