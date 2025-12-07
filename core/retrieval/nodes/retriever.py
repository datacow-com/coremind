from qdrant_client.models import FieldCondition, Filter, MatchValue

from core.embedding.registry import get_embedder
from core.state import RetrievalState, RetrievedChunk
from core.storage.kb_config import load_kb_config
from core.storage.keyword_store import get_keyword_client
from core.storage.vector_store import get_vector_client
from core.utils.monitor import retrieval_latency


class HybridRetriever:
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        with retrieval_latency.time():
            cfg = state["strategy_config"]
            queries = state["preprocessed_queries"]
            kb_name = state["kb_name"]
            kb_cfg = load_kb_config(kb_name) if kb_name else {}
            top_k = cfg.get("top_k", kb_cfg.get("top_k_default", 10))
            intent = state.get("intent", {})

            vector_client = get_vector_client()
            keyword_client = get_keyword_client()
            embedder = get_embedder(model_name=cfg.get("embedding_model"))

            vector_results: list[dict] = []
            keyword_results: list[dict] = []

            # Build Intent Filters
            qdrant_filter = None
            es_filters = {}

            intent_type = intent.get("type")
            filters = intent.get("filters", {})

            # Determine required filters based on intent
            # E.g., if "table_query", force block_type='table'
            # E.g., language filter

            must_conditions = []

            if intent_type == "table_query":
                must_conditions.append(
                    FieldCondition(key="metadata.block_type", match=MatchValue(value="table"))
                )
                es_filters["block_type"] = "table"
            elif intent_type == "image_query":
                must_conditions.append(
                    FieldCondition(key="metadata.block_type", match=MatchValue(value="image"))
                )
                es_filters["block_type"] = "image"

            # Language filter if present
            lang = filters.get("lang")
            if lang:
                must_conditions.append(
                    FieldCondition(key="metadata.language", match=MatchValue(value=lang))
                )
                es_filters["language"] = lang

            # Apply filters if any
            if must_conditions:
                qdrant_filter = Filter(must=must_conditions)

            # Execute Search（向量/关键词并行）
            import asyncio

            async def _search_once(q: str):
                if asyncio.iscoroutinefunction(embedder.embed):
                    vec = await embedder.embed(q)
                else:
                    vec = await asyncio.to_thread(embedder.embed, q)

                async def _v():
                    return await vector_client.search(
                        collection_name=kb_cfg.get("collection_name")
                        or f"kb_{kb_name}_v{kb_cfg.get('version', 1)}",
                        query_vector=vec.tolist(),
                        limit=top_k * 2,
                        query_filter=qdrant_filter,
                    )

                async def _k():
                    return await keyword_client.search(
                        index_name=f"kb_{kb_name}_docs",
                        query=q,
                        limit=top_k * 2,
                        filters=es_filters,
                    )

                v_res, k_res = await asyncio.gather(_v(), _k())
                return v_res, k_res

            for query in queries:
                v_res, k_res = await _search_once(query)
                vector_results.extend(v_res)
                keyword_results.extend(k_res)

            # RRF Fusion
            fused = self._rrf_fusion(
                vector_results, keyword_results, k=int(cfg.get("rrf_k", kb_cfg.get("rrf_k", 60)))
            )

            # Convert to State format
            state["vector_results"] = [self._to_chunk(r) for r in vector_results]
            state["keyword_results"] = [self._to_chunk(r) for r in keyword_results]

            # Top K after fusion
            state["fused_results"] = fused[:top_k]

            return state

    def _to_chunk(self, res: dict) -> RetrievedChunk:
        return {
            "id": str(res.get("id")),
            "content": res.get("content"),
            "page_num": res.get("metadata", {}).get("page_num", 0),
            "doc_id": res.get("metadata", {}).get("doc_id", ""),
            "chunk_index": res.get("metadata", {}).get("chunk_index", 0),
            "metadata": res.get("metadata", {}),
            "score": res.get("score", 0.0),
            "rerank_score": None,
        }

    def _rrf_fusion(
        self, vec_res: list[dict], kw_res: list[dict], k: int = 60
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        # Rank Vector
        vec_res.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(vec_res):
            doc_id = str(item["id"])
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            docs[doc_id] = item

        # Rank Keyword
        kw_res.sort(key=lambda x: x["score"], reverse=True)
        for rank, item in enumerate(kw_res):
            doc_id = str(item["id"])
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = item

        # Sort by RRF score
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        fused_chunks = []
        for doc_id, score in sorted_ids:
            chunk = self._to_chunk(docs[doc_id])
            chunk["score"] = score
            fused_chunks.append(chunk)

        return fused_chunks
