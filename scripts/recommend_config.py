import argparse
import json
from typing import Any

import httpx

from core.nodes.retrieve import retrieve


def load_queries(path: str) -> list[str]:
    qs: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            q = str(obj.get("query") or "").strip()
            if q:
                qs.append(q)
    return qs


async def eval_params(queries: list[str], params: dict[str, Any]) -> dict[str, Any]:
    scores: list[float] = []
    for q in queries:
        out = await retrieve({"query": q, "metadata": params})
        s = sum([float(c.get("score") or 0.0) for c in out.get("retrieved_chunks") or []])
        scores.append(s)
    avg = (sum(scores) / max(len(scores), 1)) if scores else 0.0
    return {"avg": avg, "params": params}


def choose_best(reports: list[dict[str, Any]]) -> dict[str, Any]:
    best = (
        max(reports, key=lambda r: float(r.get("avg") or 0.0))
        if reports
        else {"avg": 0.0, "params": {}}
    )
    return best["params"]


def apply_settings(base_url: str, payload: dict[str, Any]) -> None:
    with httpx.Client(timeout=15.0) as client:
        client.post(f"{base_url}/api/system/settings/update", json=payload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("queries", help="path to jsonl with entries {query}")
    ap.add_argument("--base_url", default="http://127.0.0.1:8000")
    ap.add_argument("--doc", dest="doc_path", default=None)
    args = ap.parse_args()
    queries = load_queries(args.queries)
    import asyncio

    grid = [
        {"top_k": 8, "vector_weight": 0.7, "keyword_weight": 0.3},
        {"top_k": 10, "vector_weight": 0.6, "keyword_weight": 0.4},
        {"top_k": 12, "vector_weight": 0.5, "keyword_weight": 0.5},
    ]
    reports: list[dict[str, Any]] = []
    for p in grid:
        if args.doc_path:
            p["doc_paths"] = [args.doc_path]
        rep = asyncio.get_event_loop().run_until_complete(eval_params(queries, p))
        reports.append(rep)
    best = choose_best(reports)
    payload = {
        "top_k": int(best.get("top_k") or 8),
        "vector_weight": float(best.get("vector_weight") or 0.6),
        "keyword_weight": float(best.get("keyword_weight") or 0.4),
    }
    apply_settings(args.base_url, payload)
    print(json.dumps({"applied": payload, "reports": reports}, ensure_ascii=False))


if __name__ == "__main__":
    main()
