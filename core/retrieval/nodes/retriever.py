from qdrant_client.models import FieldCondition, Filter, MatchValue

from core.embedding.registry import get_embedder
from core.state import RetrievalState, RetrievedChunk
from core.storage.channel_utils import channel_collection_name, channel_index_name
from core.storage.kb_config import load_kb_config
from core.storage.keyword_store import get_keyword_client
from core.storage.vector_store import get_vector_client
from core.utils.monitor import retrieval_latency


class HybridRetriever:
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        with retrieval_latency.time():
            cfg = state["strategy_config"]
            queries = state["preprocessed_queries"]
            channel_id = state.get("channel_id")  # Multi-channel support

            # Support both kb_names (list) and kb_name (string) for compatibility
            kb_names = state.get("kb_names") or []
            if not kb_names and state.get("kb_name"):
                kb_names = [state.get("kb_name")]

            top_k = cfg.get("top_k", 10)
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

            if must_conditions:
                qdrant_filter = Filter(must=must_conditions)

            import asyncio

            async def _search_kb(kb_name: str, q: str):
                """Search a single KB with channel isolation."""
                kb_cfg = load_kb_config(kb_name) if kb_name else {}
                version = kb_cfg.get("version", 1)

                if asyncio.iscoroutinefunction(embedder.embed):
                    vec = await embedder.embed(q)
                else:
                    vec = await asyncio.to_thread(embedder.embed, q)

                async def _v():
                    # Use channel-aware collection name
                    collection = kb_cfg.get("collection_name") or channel_collection_name(
                        channel_id, kb_name, version
                    )
                    return await vector_client.search(
                        collection_name=collection,
                        query_vector=vec.tolist(),
                        limit=top_k * 2,
                        query_filter=qdrant_filter,
                    )

                async def _k():
                    # Use channel-aware index name
                    index_name = channel_index_name(channel_id, kb_name)
                    return await keyword_client.search(
                        index_name=index_name,
                        query=q,
                        limit=top_k * 2,
                        filters=es_filters,
                    )

                v_res, k_res = await asyncio.gather(_v(), _k())
                return v_res, k_res

            # Search across all KBs and queries
            for query in queries:
                for kb_name in kb_names:
                    v_res, k_res = await _search_kb(kb_name, query)
                    vector_results.extend(v_res)
                    keyword_results.extend(k_res)

            # RRF Fusion - use cfg directly (kb_cfg is only available inside _search_kb)
            fused = self._rrf_fusion(
                vector_results, keyword_results, k=int(cfg.get("rrf_k", 60))
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
