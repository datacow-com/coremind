def classify_blocks_layoutlm(
    image_bytes: bytes, boxes: list[tuple[int, int, int, int]], model_name: str
) -> list[str]:
    try:
        from io import BytesIO

        import torch
        from PIL import Image
        from transformers import LayoutLMv3ForSequenceClassification, LayoutLMv3Processor
    except Exception:
        return ["" for _ in boxes]
    try:
        processor = LayoutLMv3Processor.from_pretrained(model_name)
        model = LayoutLMv3ForSequenceClassification.from_pretrained(model_name)
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
