import argparse
import json

from core.reranker.cohere_reranker import CohereReranker
from core.reranker.cross_encoder import Reranker


def load_dataset(path: str) -> list[dict]:
    items: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("query") and obj.get("texts"):
                items.append(obj)
    return items


def evaluate(items: list[dict]) -> dict:
    ce = Reranker()
    co = CohereReranker()
    use_co = co.available()
    reports = []
    for it in items:
        q = str(it.get("query"))
        texts = list(it.get("texts"))
        ce_scores = ce.score(q, texts)
        co_scores = co.score(q, texts) if use_co else [0.0 for _ in texts]
        ce_top = sorted([(i, s) for i, s in enumerate(ce_scores)], key=lambda x: -x[1])[:10]
        co_top = sorted([(i, s) for i, s in enumerate(co_scores)], key=lambda x: -x[1])[:10]
        reports.append(
            {
                "query": q,
                "crossencoder_top10": [int(i) for i, _ in ce_top],
                "cohere_top10": [int(i) for i, _ in co_top],
                "crossencoder_scores": ce_scores,
                "cohere_scores": co_scores,
            }
        )
    return {"use_cohere": use_co, "count": len(items), "reports": reports}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", help="path to jsonl with {query, texts[]} entries")
    args = ap.parse_args()
    items = load_dataset(args.dataset)
    result = evaluate(items)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
