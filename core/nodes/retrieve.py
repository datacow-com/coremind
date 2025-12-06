import asyncio
import time
from typing import Any

from core.embedding.registry import get_embedder
from core.pipeline.kb_merge import merge_kb_params
from core.state import RAGState, RetrievedChunk
from core.storage.index_router import search as search_index
from core.storage.keyword_index import get_keyword_index
from core.utils.trace import set_span_attrs
from server.config import settings


async def retrieve(state: RAGState) -> dict:
    query = state.get("query", "")
    if not query:
        return {"retrieved_chunks": [], "step": "retrieval"}

    emb_provider = (state.get("metadata") or {}).get("embedder_provider")
    emb_model = (state.get("metadata") or {}).get("embedder_model")
    emb = get_embedder(dim=256, provider=emb_provider, model_name=emb_model)
    qvec = await asyncio.to_thread(emb.embed, query)
    meta_state = merge_kb_params(state.get("metadata", {}) or {})
    v_weight = float(meta_state.get("vector_weight"))
    k_weight = float(meta_state.get("keyword_weight"))
    top_k = int(meta_state.get("top_k"))
    candidate_k = int(meta_state.get("candidate_k"))
    doc_paths = meta_state.get("doc_paths") or None
    kb_name = meta_state.get("kb_name") or None
    t0 = time.perf_counter()

    # 语言提示：用于双栈集合选择
    def _lang_hint(text: str) -> str:
        t = (text or "").strip()
        if not t:
            return "en"
        total = len(t)
        cjk = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
        return "cn" if (total and (cjk / total) >= 0.2) else "en"

    k_rrf = int(meta_state.get("rrf_k") or getattr(settings, "rrf_k", 60))
    use_base = bool(settings.use_base_retriever)
    lang_hint_override = str(meta_state.get("lang_hint") or "").strip() or None
    if not lang_hint_override and kb_cfg:
        st = str(kb_cfg.get("stack") or "").lower()
        if st in {"cn", "en"}:
            lang_hint_override = st
    vector_results: list[tuple[dict[str, Any], float]] = []
    if use_base:
        try:
            from core.retriever.base_retriever import OmniIndexRetriever

            retr = OmniIndexRetriever(top_k=candidate_k)
            docs = retr.invoke(query)
            # map to [(meta, score)]
            tmp = []
            for d in docs:
                meta = dict(d.metadata or {})
                score = float(meta.get("score") or 0.0)
                tmp.append((meta, score))
            vector_results = tmp
        except Exception:
            vector_results = search_index(
                qvec, top_k=candidate_k, lang_hint=lang_hint_override or _lang_hint(query)
            )
    else:
        collection_name = None
        backend_override = None
        try:
            if kb_cfg:
                collection_name = (kb_cfg.get("collection_name") or "") or None
                backend_override = (kb_cfg.get("vector_backend") or "") or None
        except Exception:
            collection_name = None
            backend_override = None
        vector_results = search_index(
            qvec,
            top_k=candidate_k,
            lang_hint=lang_hint_override or _lang_hint(query),
            collection_name=collection_name,
            backend_override=backend_override,
        )
    kw = get_keyword_index()
    keyword_results = kw.search(query, top_k=candidate_k)

    if doc_paths:

        def keep(m: dict[str, Any]) -> bool:
            return m.get("doc_id") in doc_paths

        vector_results = [(m, s) for (m, s) in vector_results if keep(m)]
        keyword_results = [(m, s) for (m, s) in keyword_results if keep(m)]

    # RRF 融合：Score(d) = Σ 1 / (k + rank_path(d))
    # 先基于各通道得分计算排名（高分排前）
    def to_rank_map(results: list[tuple[dict[str, Any], float]]) -> dict[str, int]:
        sorted_list = sorted(results, key=lambda t: float(t[1]), reverse=True)
        rank_map: dict[str, int] = {}
        for idx, (m, _s) in enumerate(sorted_list, start=1):
            rid = m.get("id")
            if rid not in rank_map:
                rank_map[str(rid)] = idx
        return rank_map

    def _norm_scores(
        results: list[tuple[dict[str, Any], float]],
    ) -> list[tuple[dict[str, Any], float]]:
        if not results:
            return []
        vals = [float(s) for _, s in results]
        mn, mx = min(vals), max(vals)
        if mx - mn < 1e-6:
            return [(m, 0.5) for m, _ in results]
        return [(m, (float(s) - mn) / (mx - mn)) for m, s in results]

    vec_rank = to_rank_map([(m, s * v_weight) for (m, s) in _norm_scores(vector_results)])
    kw_rank = to_rank_map([(m, s * k_weight) for (m, s) in _norm_scores(keyword_results)])

    k_rrf = int(locals().get("k_rrf", getattr(settings, "rrf_k", 60)))
    fused: dict[str, RetrievedChunk] = {}

    def ensure(meta: dict[str, Any]) -> RetrievedChunk:
        rid = str(meta.get("id"))
        existing = fused.get(rid)
        if not existing:
            fused[rid] = {
                "id": rid,
                "content": str(meta.get("content") or ""),
                "page_num": int(meta.get("page_num") or 0),
                "doc_id": str(meta.get("doc_id") or ""),
                "chunk_index": int(meta.get("chunk_index") or 0),
                "metadata": meta.get("metadata", {}),
                "score": 0.0,
                "rerank_score": None,
            }
        return fused[rid]

    # 聚合所有出现过的文档ID
    all_ids = set(list(vec_rank.keys()) + list(kw_rank.keys()))
    for rid in all_ids:
        # 取任一来源的 meta（优先向量通道）
        chunk_meta: dict[str, Any] | None = None
        for mvec, _ in vector_results:
            if mvec.get("id") == rid:
                chunk_meta = mvec
                break
        if chunk_meta is None:
            for mkw, _ in keyword_results:
                if mkw.get("id") == rid:
                    chunk_meta = mkw
                    break
        if chunk_meta is None:
            # 防御性：若找不到元数据则跳过
            continue
        item = ensure(chunk_meta)
        rrf_score = 0.0
        if rid in vec_rank:
            rrf_score += 1.0 / (k_rrf + vec_rank[rid])
        if rid in kw_rank:
            rrf_score += 1.0 / (k_rrf + kw_rank[rid])
        # feature weighting based on block type and heading level
        meta_md = item.get("metadata") or {}
        btype = str(meta_md.get("block_type") or meta_md.get("type") or "").lower()
        hlevel_val = meta_md.get("heading_level")
        try:
            hlevel = int(hlevel_val) if hlevel_val is not None else None
        except Exception:
            hlevel = None
        weight = 1.0
        if btype == "heading":
            weight = 1.3 if (hlevel is not None and hlevel <= 2) else 1.15
        elif btype == "table":
            weight = 1.2
        elif btype == "figure":
            weight = 0.9
        elif btype == "paragraph" or btype == "visual":
            weight = 1.0
        item["score"] = float(rrf_score * weight)

    results: list[RetrievedChunk] = list(fused.values())
    retrieved: list[RetrievedChunk] = sorted(
        results, key=lambda x: x.get("score", 0.0), reverse=True
    )[:candidate_k]
    dur = int((time.perf_counter() - t0) * 1000)
    set_span_attrs(
        {
            "retrieval.embedder": emb_provider or "auto",
            "retrieval.vector_weight": v_weight,
            "retrieval.keyword_weight": k_weight,
            "retrieval.top_k": top_k,
            "retrieval.candidate_k": candidate_k,
            "retrieval.duration_ms": dur,
        }
    )
    return {
        "retrieved_chunks": retrieved,
        "step": "retrieval",
        "metrics": {"retrieve": {"count": len(retrieved), "duration_ms": dur}},
    }
