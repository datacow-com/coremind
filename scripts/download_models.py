import argparse
import os
import sys
from pathlib import Path


def download_yolo(dst: Path, filename: str) -> Path:
    import httpx

    urls = [
        os.environ.get(
            "YOLO_DOWNLOAD_URL",
            "https://huggingface.co/ultralytics/YOLOv8/resolve/main/yolov8n.pt",
        ),
        "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
    ]
    dst.mkdir(parents=True, exist_ok=True)
    out = dst / filename
    if out.exists() and out.stat().st_size > 0:
        return out
    last_err: Exception | None = None
    for url in urls:
        try:
            with httpx.Client(timeout=60.0) as http:
                r = http.get(url, follow_redirects=True)
                r.raise_for_status()
                out.write_bytes(r.content)
                return out
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return out


def cache_layoutlm(model_name: str, cache_dir: Path) -> Path:
    from transformers import LayoutLMv3Model, LayoutLMv3Processor

    cache_dir.mkdir(parents=True, exist_ok=True)
    LayoutLMv3Processor.from_pretrained(model_name, cache_dir=str(cache_dir))
    LayoutLMv3Model.from_pretrained(model_name, cache_dir=str(cache_dir))
    return cache_dir / model_name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo-file", default="yolov8n.pt")
    ap.add_argument("--layoutlm-model", default="microsoft/layoutlmv3-base")
    ap.add_argument("--out", default="models")
    args = ap.parse_args()

    root = Path(args.out)
    yolo_dir = root / "yolo"
    hf_dir = root / "hf"

    try:
        yolo_path = download_yolo(yolo_dir, args.yolo_file)
        print(f"YOLO saved: {yolo_path}")
    except Exception as e:
        print(f"Failed to download YOLO: {e}", file=sys.stderr)
        yolo_path = None

    try:
        lm_path = cache_layoutlm(args.layoutlm_model, hf_dir)
        print(f"LayoutLMv3 cached under: {lm_path}")
    except Exception as e:
        print(f"Failed to cache LayoutLMv3: {e}", file=sys.stderr)
        lm_path = None

    print("Suggested environment configuration:")
    if yolo_path is not None:
        print("  export YOLO_ENABLED=1")
        print(f"  export YOLO_MODEL={yolo_path}")
    if lm_path is not None:
        print("  export LAYOUTLM_ENABLED=1")
        print(f"  export LAYOUTLM_MODEL={args.layoutlm_model}")


if __name__ == "__main__":
    main()
