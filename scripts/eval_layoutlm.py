import argparse
import json
from pathlib import Path

from core.loaders.visual_pdf_loader import ParsingRule, VisualPDFLoader


async def evaluate(pdf_path: str, class_model: str | None) -> dict:
    loader = VisualPDFLoader(ParsingRule())
    pages = await loader._pdf_pages(pdf_path)
    total_blocks = 0
    dist: dict[str, int] = {}
    for i in range(len(pages)):
        cache_key = f"{pdf_path}#p{i+1}"
        blocks = loader._block_cache.get(cache_key, []) or []
        total_blocks += len(blocks)
        for txt, _ in blocks:
            bt = (txt or "").lower()
            if bt not in {"paragraph", "heading", "table", "figure"}:
                bt = "unknown"
            dist[bt] = dist.get(bt, 0) + 1
    return {
        "pdf": pdf_path,
        "total_blocks": total_blocks,
        "distribution": dist,
        "class_model": class_model,
    }


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
