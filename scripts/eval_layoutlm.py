import argparse
import json
from pathlib import Path


async def evaluate(pdf_path: str, class_model: str | None) -> dict:
    # VisualPDFLoader 已废弃并会抛异常；本脚本保留入口但明确提示。
    raise RuntimeError(
        "scripts/eval_layoutlm.py relies on VisualPDFLoader which is no longer supported. "
        "Please migrate to the LangGraph ingestion pipeline (GpuVisionParser + SmartChunker) "
        "and add evaluation there."
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", default="data/samples/pdf/arxiv_sample.pdf")
    ap.add_argument("--class_model", default=None)
    ap.add_argument("--out", default="reports/layoutlm_eval.json")
    args = ap.parse_args()
    import asyncio

    rep = asyncio.get_event_loop().run_until_complete(evaluate(args.pdf, args.class_model))
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved report: {outp}")


if __name__ == "__main__":
    main()
