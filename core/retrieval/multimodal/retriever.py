"""
Multimodal Retriever - Cross-modal search across text, images, and tables.

Features:
- Text-to-image search
- Image-to-text search
- Cross-modal fusion
- Modality-aware ranking
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from core.retrieval.multimodal.embedder import ModalityType, MultimodalEmbedder
from core.state import RetrievalState

try:
    from core.utils.monitor import retrieval_duration
except ImportError:
    retrieval_duration = None

logger = logging.getLogger(__name__)


@dataclass
class MultimodalResult:
    """Represents a multimodal search result."""

    id: str
    content: str
    modality: ModalityType
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    # Optional additional data
    image_data: bytes | None = None
    table_data: str | None = None
    source_doc: str | None = None
    page: int | None = None
    bbox: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "modality": self.modality,
            "score": self.score,
            "metadata": self.metadata,
            "source_doc": self.source_doc,
            "page": self.page,
            "bbox": self.bbox,
        }


class MultimodalRetriever:
    """
    Retrieves relevant content across multiple modalities.

    This capability supports:
    - Text queries finding images/tables
    - Image queries finding similar images or related text
    - Unified ranking across modalities
    - Modality-specific filtering

    Configuration:
        enable_image_search: bool - Include image results
        enable_table_search: bool - Include table results
        cross_modal_weight: float - Weight for cross-modal matches
        modality_filter: list[str] - Filter results by modality
        top_k: int - Number of results per modality
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.enable_image_search = self.config.get("enable_image_search", True)
        self.enable_table_search = self.config.get("enable_table_search", True)
        self.cross_modal_weight = self.config.get("cross_modal_weight", 0.8)
        self.modality_filter = self.config.get("modality_filter", None)
        self.top_k = self.config.get("top_k", 5)

        self.embedder = MultimodalEmbedder(self.config.get("embedder_config"))
        self._semaphore = asyncio.Semaphore(3)

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        """Process retrieval state with multimodal search."""
        if retrieval_duration:
            with retrieval_duration.labels(stage="multimodal_retriever").time():
                return await self.retrieve(state)
        return await self.retrieve(state)

    async def retrieve(self, state: RetrievalState) -> RetrievalState:
        """
        Perform multimodal retrieval based on query.

        Enhances standard retrieval with cross-modal results.
        """
        query = state.get("input_query", "")
        kb_names = state.get("kb_names", [])
        
        # P0 Fix: Enforce channel_id for multi-tenant isolation
        channel_id = state.get("channel_id")
        if not channel_id:
            logger.warning("channel_id not provided, multimodal retrieval requires tenant isolation")
            if "error_log" not in state:
                state["error_log"] = []
            state["error_log"].append({
                "stage": "multimodal_retriever",
                "error": "channel_id is required for multi-tenant isolation",
            })
            return state

        if not query or not kb_names:
            return state

        async with self._semaphore:
            try:
                # Detect query modality
                query_modality = self._detect_query_modality(state)

                # Generate query embedding
                if query_modality == "image":
                    query_data = state.get("query_image")
                    query_embedding = await self.embedder.embed(query_data, "image")
                else:
                    query_embedding = await self.embedder.embed(query, "text")

                # Search each KB
                all_results: list[MultimodalResult] = []

                for kb_name in kb_names:
                    results = await self._search_kb(
                        kb_name=kb_name,
                        query_embedding=query_embedding,
                        query_modality=query_modality,
                        query_text=query,
                        channel_id=channel_id,  # Pass channel_id
                    )
                    all_results.extend(results)

                # Apply modality filter if specified
                if self.modality_filter:
                    all_results = [r for r in all_results if r.modality in self.modality_filter]

                # Rank and merge with existing results
                ranked_results = self._rank_results(all_results, query_modality)

                # Merge with standard retrieval results
                state = self._merge_with_state(state, ranked_results)

            except Exception as e:
                logger.error(f"Multimodal retrieval failed: {e}")
                if "error_log" not in state:
                    state["error_log"] = []
                state["error_log"].append(
                    {
                        "stage": "multimodal_retriever",
                        "error": str(e),
                    }
                )

        return state

    async def search(
        self,
        query: str | bytes,
        kb_names: list[str],
        channel_id: str,  # P0 Fix: Required for multi-tenant isolation
        modality: ModalityType = "text",
        top_k: int | None = None,
    ) -> list[MultimodalResult]:
        """
        Direct search API for multimodal queries.

        Args:
            query: Text string or image bytes
            kb_names: Knowledge bases to search
            channel_id: Required channel identifier for tenant isolation
            modality: Query modality type
            top_k: Number of results to return

        Returns:
            List of MultimodalResult
            
        Raises:
            ValueError: If channel_id is not provided
        """
        # P0 Fix: Enforce channel_id for multi-tenant isolation
        if not channel_id:
            raise ValueError("channel_id is required for multi-tenant isolation")
        
        k = top_k or self.top_k

        # Generate query embedding
        query_embedding = await self.embedder.embed(query, modality)

        all_results = []
        for kb_name in kb_names:
            results = await self._search_kb(
                kb_name=kb_name,
                query_embedding=query_embedding,
                query_modality=modality,
                query_text=query if modality == "text" else "",
                channel_id=channel_id,  # P0 Fix: Pass channel_id for isolation
            )
            all_results.extend(results)

        # Rank and return top k
        ranked = self._rank_results(all_results, modality)
        return ranked[:k]

    async def _search_kb(
        self,
        kb_name: str,
        query_embedding: list[float],
        query_modality: ModalityType,
        query_text: str = "",
        channel_id: str | None = None,
    ) -> list[MultimodalResult]:
        """Search a single knowledge base with channel isolation.
        
        Args:
            kb_name: Knowledge base name
            query_embedding: Query vector
            query_modality: Query modality type
            query_text: Original query text
            channel_id: Required channel identifier for tenant isolation
            
        Raises:
            ValueError: If channel_id is not provided
        """
        # P0 Fix: Enforce channel_id for multi-tenant isolation
        if not channel_id:
            raise ValueError("channel_id is required for multi-tenant isolation")
        results = []

        # Search text chunks
        text_results = await self._search_text_vectors(kb_name, query_embedding, query_text, channel_id)
        results.extend(text_results)

        # Search image embeddings if enabled
        if self.enable_image_search:
            image_results = await self._search_image_vectors(kb_name, query_embedding, channel_id)
            results.extend(image_results)

        # Search table embeddings if enabled
        if self.enable_table_search:
            table_results = await self._search_table_vectors(kb_name, query_embedding, channel_id)
            results.extend(table_results)

        return results

    async def _search_text_vectors(
        self,
        kb_name: str,
        query_embedding: list[float],
        query_text: str,
        channel_id: str,  # P0 Fix: Required, no default
    ) -> list[MultimodalResult]:
        """Search text vectors in Qdrant with channel isolation."""
        try:
            from core.storage.channel_utils import channel_collection_name
            from core.storage.vector_store import QdrantVectorStore

            # Get collection name with channel isolation
            collection = channel_collection_name(channel_id, kb_name)

            store = QdrantVectorStore()

            # Vector search
            hits = await store.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=self.top_k * 2,  # Get more for fusion
            )

            results = []
            for hit in hits:
                payload = hit.payload or {}

                # Skip non-text or use modality from payload
                block_type = payload.get("block_type", "text")
                if block_type in ("image", "table"):
                    modality = block_type
                else:
                    modality = "text"

                results.append(
                    MultimodalResult(
                        id=str(hit.id),
                        content=payload.get("content", ""),
                        modality=modality,
                        score=hit.score,
                        metadata=payload.get("metadata", {}),
                        source_doc=payload.get("doc_id"),
                        page=payload.get("page_num"),
                        bbox=payload.get("bbox"),
                    )
                )

            return results

        except Exception as e:
            logger.warning(f"Text vector search failed: {e}")
            return []

    async def _search_image_vectors(
        self,
        kb_name: str,
        query_embedding: list[float],
        channel_id: str,  # P0 Fix: Required, no default
    ) -> list[MultimodalResult]:
        """Search image-specific collection with channel isolation."""
        try:
            from core.storage.channel_utils import channel_collection_name
            from core.storage.vector_store import QdrantVectorStore

            # Image collection with channel prefix
            base_collection = channel_collection_name(channel_id, kb_name)
            collection = f"{base_collection}_images"

            store = QdrantVectorStore()

            # Check if collection exists
            if not await store.collection_exists(collection):
                return []

            hits = await store.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=self.top_k,
            )

            results = []
            for hit in hits:
                payload = hit.payload or {}
                results.append(
                    MultimodalResult(
                        id=str(hit.id),
                        content=payload.get("description", payload.get("content", "")),
                        modality="image",
                        score=hit.score * self.cross_modal_weight,  # Apply cross-modal weight
                        metadata=payload.get("metadata", {}),
                        source_doc=payload.get("doc_id"),
                        page=payload.get("page_num"),
                        bbox=payload.get("bbox"),
                    )
                )

            return results

        except Exception as e:
            logger.debug(f"Image vector search not available: {e}")
            return []

    async def _search_table_vectors(
        self,
        kb_name: str,
        query_embedding: list[float],
        channel_id: str,  # P0 Fix: Required, no default
    ) -> list[MultimodalResult]:
        """Search table-specific collection with channel isolation."""
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            from core.storage.channel_utils import channel_collection_name
            from core.storage.vector_store import QdrantVectorStore

            # Table vectors are indexed into dedicated *_tables collection
            base_collection = channel_collection_name(channel_id, kb_name)
            collection = f"{base_collection}_tables"

            store = QdrantVectorStore()

            # Collection guard: if tables were not indexed, degrade gracefully
            if not await store.collection_exists(collection):
                return []

            # Search with table filter
            table_filter = Filter(
                must=[FieldCondition(key="block_type", match=MatchValue(value="table"))]
            )

            hits = await store.search(
                collection_name=collection,
                query_vector=query_embedding,
                limit=self.top_k,
                query_filter=table_filter,
            )

            results = []
            for hit in hits:
                payload = hit.payload or {}
                results.append(
                    MultimodalResult(
                        id=str(hit.id),
                        content=payload.get("content", ""),
                        modality="table",
                        score=hit.score,
                        metadata=payload.get("metadata", {}),
                        table_data=payload.get("table_content"),
                        source_doc=payload.get("doc_id"),
                        page=payload.get("page_num"),
                        bbox=payload.get("bbox"),
                    )
                )

            return results

        except Exception as e:
            logger.debug(f"Table vector search not available: {e}")
            return []

    def _detect_query_modality(self, state: RetrievalState) -> ModalityType:
        """Detect the modality of the query."""
        # Check if query contains image
        if state.get("query_image"):
            return "image"

        # Check for table-related keywords
        query = state.get("input_query", "").lower()
        table_keywords = ["table", "表格", "数据", "统计", "对比"]
        if any(kw in query for kw in table_keywords):
            # Still text query, but may want table results
            pass

        return "text"

    def _rank_results(
        self,
        results: list[MultimodalResult],
        query_modality: ModalityType,
    ) -> list[MultimodalResult]:
        """Rank results considering cross-modal matching."""
        if not results:
            return results

        # Apply modality-specific scoring adjustments
        for result in results:
            # Boost same-modality matches
            if result.modality == query_modality:
                result.score *= 1.1

            # Apply cross-modal weight for different modalities
            elif query_modality == "text" and result.modality == "image":
                result.score *= self.cross_modal_weight
            elif query_modality == "image" and result.modality == "text":
                result.score *= self.cross_modal_weight

        # Sort by adjusted score
        return sorted(results, key=lambda r: r.score, reverse=True)

    def _merge_with_state(
        self,
        state: RetrievalState,
        multimodal_results: list[MultimodalResult],
    ) -> RetrievalState:
        """Merge multimodal results with existing retrieval state."""
        # Convert to chunk format for compatibility
        chunks = []
        for result in multimodal_results[: self.top_k]:
            chunk = {
                "id": result.id,
                "content": result.content,
                "page_num": result.page,
                "doc_id": result.source_doc,
                "chunk_index": 0,
                "score": result.score,
                "rerank_score": None,
                "metadata": {
                    **result.metadata,
                    "modality": result.modality,
                    "multimodal_search": True,
                },
            }
            chunks.append(chunk)

        # Add to existing results
        existing = state.get("fused_results", [])
        combined = list(existing) + chunks

        # Re-sort by score
        combined.sort(key=lambda c: c.get("score", 0), reverse=True)

        state["fused_results"] = combined

        # Also update multimodal-specific field
        state["multimodal_results"] = [r.to_dict() for r in multimodal_results]

        return state


# Factory function
def create_multimodal_retriever(config: dict[str, Any] | None = None) -> MultimodalRetriever:
    """Factory function for creating MultimodalRetriever instances."""
    return MultimodalRetriever(config)
