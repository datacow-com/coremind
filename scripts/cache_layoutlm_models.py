import argparse
from pathlib import Path


def cache_class_model(model_name: str, cache_dir: Path) -> Path:
    from transformers import AutoConfig, AutoModelForSequenceClassification

    cache_dir.mkdir(parents=True, exist_ok=True)
    AutoModelForSequenceClassification.from_pretrained(model_name, cache_dir=str(cache_dir))
    cfg = AutoConfig.from_pretrained(model_name, cache_dir=str(cache_dir))
    id2label = getattr(cfg, "id2label", None)
    if not id2label:
        raise RuntimeError("Model lacks id2label mapping; choose a fine-tuned classification model")
    return cache_dir / model_name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nielsr/layoutlmv3-finetuned-funsd")
    ap.add_argument("--out", default="models/hf")
    args = ap.parse_args()

    p = cache_class_model(args.model, Path(args.out))
    print(f"LayoutLMv3 classification model cached under: {p}")
    print("Suggested env vars:")
    print(f"  export LAYOUTLM_CLASS_MODEL={args.model}")


if __name__ == "__main__":
    main()
