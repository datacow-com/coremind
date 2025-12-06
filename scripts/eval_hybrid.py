import argparse
import json
from typing import Any

from core.nodes.retrieve import retrieve


def load_dataset(path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("query"):
                items.append(obj)
    return items


async def run_eval(items: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    scores: list[float] = []
    for it in items:
        state = {"query": it["query"], "metadata": params}
        out = await retrieve(state)
        s = sum([float(c.get("score") or 0.0) for c in out.get("retrieved_chunks") or []])
        scores.append(s)
    avg = (sum(scores) / max(len(scores), 1)) if scores else 0.0
    return {"avg_score": avg, "count": len(items), "params": params}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="path to jsonl with entries {query}")
    ap.add_argument("--doc", dest="doc_path", default=None)
    args = ap.parse_args()
    items = load_dataset(args.dataset)
    import asyncio

    grid = [
        {"top_k": 5, "vector_weight": 0.6, "keyword_weight": 0.4},
        {"top_k": 8, "vector_weight": 0.7, "keyword_weight": 0.3},
        {"top_k": 10, "vector_weight": 0.5, "keyword_weight": 0.5},
    ]
    reports = []
    for p in grid:
        if args.doc_path:
            p["doc_paths"] = [args.doc_path]
        rep = asyncio.get_event_loop().run_until_complete(run_eval(items, p))
        reports.append(rep)
    print(json.dumps({"reports": reports}, ensure_ascii=False))


if __name__ == "__main__":
    main()
