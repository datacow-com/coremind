from typing import Dict, List
import time
from core.state import RAGState, RetrievedChunk
from core.embedding.provider_embedder import Embedder
from core.storage.index_router import search as search_index
from core.storage.keyword_index import get_keyword_index
import os


async def retrieve(state: RAGState) -> Dict:
    query = state.get("query", "")
    if not query:
        return {"retrieved_chunks": [], "step": "retrieval"}

    emb = Embedder(dim=256)
    qvec = emb.embed(query)
    meta = state.get("metadata", {}) or {}
    v_weight = float(meta.get("vector_weight") or os.environ.get("VECTOR_WEIGHT", "0.6"))
    k_weight = float(meta.get("keyword_weight") or os.environ.get("KEYWORD_WEIGHT", "0.4"))
    top_k = int(meta.get("top_k") or 5)
    doc_paths = meta.get("doc_paths") or None
    t0 = time.perf_counter()
    vector_results = search_index(qvec, top_k=top_k)
    kw = get_keyword_index()
    keyword_results = kw.search(query, top_k=top_k)

    if doc_paths:
        def keep(meta):
            return (meta.get("doc_id") in doc_paths)
        vector_results = [(m, s) for (m, s) in vector_results if keep(m)]
        keyword_results = [(m, s) for (m, s) in keyword_results if keep(m)]

    # RRF 融合：Score(d) = Σ 1 / (k + rank_path(d))
    # 先基于各通道得分计算排名（高分排前）
    def to_rank_map(results):
        # results: List[Tuple[meta, score]]
        sorted_list = sorted(results, key=lambda t: float(t[1]), reverse=True)
        rank_map: Dict[str, int] = {}
        for idx, (m, _s) in enumerate(sorted_list, start=1):
            rid = m.get("id")
            # 若重复出现，以最靠前排名为准
            if rid not in rank_map:
                rank_map[rid] = idx
        return rank_map

    vec_rank = to_rank_map([(m, s * v_weight) for (m, s) in vector_results])
    kw_rank = to_rank_map([(m, s * k_weight) for (m, s) in keyword_results])

    k_rrf = int(os.environ.get("RRF_K", "60"))
    fused: Dict[str, RetrievedChunk] = {}

    def ensure(meta):
        rid = meta.get("id")
        existing = fused.get(rid)
        if not existing:
            fused[rid] = {
                "id": rid,
                "content": meta.get("content"),
                "page_num": meta.get("page_num"),
                "doc_id": meta.get("doc_id"),
                "chunk_index": meta.get("chunk_index"),
                "metadata": meta.get("metadata", {}),
                "score": 0.0,
                "rerank_score": None,
            }
        return fused[rid]

    # 聚合所有出现过的文档ID
    all_ids = set(list(vec_rank.keys()) + list(kw_rank.keys()))
    for rid in all_ids:
        # 取任一来源的 meta（优先向量通道）
        meta = None
        for m, _ in vector_results:
            if m.get("id") == rid:
                meta = m
                break
        if meta is None:
            for m, _ in keyword_results:
                if m.get("id") == rid:
                    meta = m
                    break
        if meta is None:
            # 防御性：若找不到元数据则跳过
            continue
        item = ensure(meta)
        rrf_score = 0.0
        if rid in vec_rank:
            rrf_score += 1.0 / (k_rrf + vec_rank[rid])
        if rid in kw_rank:
            rrf_score += 1.0 / (k_rrf + kw_rank[rid])
        item["score"] = float(rrf_score)

    results: List[RetrievedChunk] = list(fused.values())
    retrieved: List[RetrievedChunk] = sorted(results, key=lambda x: x.get("score", 0.0), reverse=True)[:top_k]
    dur = int((time.perf_counter() - t0) * 1000)
    return {"retrieved_chunks": retrieved, "step": "retrieval", "metrics": {"retrieve": {"count": len(retrieved), "duration_ms": dur}}}
