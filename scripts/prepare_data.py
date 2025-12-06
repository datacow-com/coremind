import sys
from pathlib import Path


def dl(url: str, out: Path) -> None:
    import httpx

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return
    with httpx.Client(timeout=120.0) as http:
        r = http.get(url, follow_redirects=True)
        r.raise_for_status()
        out.write_bytes(r.content)


def main() -> None:
    root = Path("data")
    pdf_dir = root / "samples" / "pdf"
    img_dir = root / "samples" / "images"
    layout_dir = root / "layoutlm"

    try:
        dl(
            "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            pdf_dir / "dummy.pdf",
        )
        dl("https://arxiv.org/pdf/2303.08774.pdf", pdf_dir / "arxiv_sample.pdf")
    except Exception as e:
        print(f"PDF download error: {e}", file=sys.stderr)

    try:
        dl("https://ultralytics.com/images/bus.jpg", img_dir / "bus.jpg")
        dl("https://ultralytics.com/images/zidane.jpg", img_dir / "zidane.jpg")
    except Exception as e:
        print(f"Image download error: {e}", file=sys.stderr)

    try:
        dl("https://guillaumejaume.github.io/FUNSD/dataset.zip", layout_dir / "funsd_dataset.zip")
    except Exception as e:
        print(f"FUNSD primary download error: {e}", file=sys.stderr)
        try:
            dl(
                "https://huggingface.co/datasets/nielsr/funsd/resolve/main/data/training_data.zip",
                layout_dir / "funsd_training.zip",
            )
        except Exception as ee:
            print(f"FUNSD fallback download error: {ee}", file=sys.stderr)

    print("Data prepared under ./data. Examples:")
    print(f"  PDFs: {pdf_dir}")
    print(f"  Images: {img_dir}")
    print(f"  LayoutLM: {layout_dir}")
    print("Use these in ingestion and parsing tests.")


if __name__ == "__main__":
    main()
