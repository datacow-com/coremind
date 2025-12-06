import os
import time

import numpy as np

from core.storage.milvus_store import MilvusStore


def main() -> None:
    dim = 256
    n = int(os.getenv("N", "1000"))
    qn = int(os.getenv("QN", "10"))
    top_k = int(os.getenv("TOPK", "10"))
    ms = MilvusStore(dim=dim, collection_name="bench_chunks")
    ms.try_init()
    vecs = np.random.rand(n, dim).astype(np.float32)
    metas = [
        {"id": f"bench-{i}", "content": "random", "doc_id": "bench", "page_num": 1}
        for i in range(n)
    ]
    t0 = time.perf_counter()
    for v, m in zip(vecs, metas, strict=False):
        ms.add(v, m)
    dur_add = time.perf_counter() - t0
    qvecs = np.random.rand(qn, dim).astype(np.float32)
    t1 = time.perf_counter()
    for q in qvecs:
        _ = ms.search(q, top_k=top_k)
    dur_search = time.perf_counter() - t1
    print(
        {
            "added": n,
            "add_time_s": round(dur_add, 4),
            "q": qn,
            "search_time_s": round(dur_search, 4),
            "avg_search_ms": round((dur_search / max(qn, 1)) * 1000, 3),
        }
    )


if __name__ == "__main__":
    main()
