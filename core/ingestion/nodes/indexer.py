from typing import Any

from qdrant_client.models import PointStruct

from core.state import IngestState
from core.storage.channel_utils import channel_collection_name, channel_index_name
from core.storage.keyword_store import get_keyword_client
from core.storage.vector_store import get_vector_client
from core.utils.monitor import ingest_duration


class DualIndexer:
    """
    Dual indexer for vector and keyword backends.

    Supports:
    - Standard text chunk indexing (Qdrant + Elasticsearch)
    - Image embedding indexing (separate collection)
    - Table-specific indexing with structured metadata
    """

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage="indexer").time():
            cfg = state["strategy_config"]
            kb_name = state["kb_name"]
            version = state["version"]
            channel_id = state.get("channel_id")  # Multi-channel support

            chunks = state["chunks"]
            vectors = state["vectors"]
            batch_size = cfg.get("index_batch_size", 500)

            # 1. Qdrant Indexing (Text Chunks)
            if cfg.get("vector_backend", "auto") != "disabled":
                await self._index_vectors(
                    state, chunks, vectors, cfg, kb_name, version, channel_id, batch_size
                )

            # 2. Elasticsearch Indexing (Keyword Search)
            if cfg.get("keyword_backend", "elasticsearch") == "elasticsearch":
                await self._index_keywords(state, chunks, cfg, kb_name, channel_id, batch_size)

            # 3. Multimodal Indexing (Images & Tables - NEW)
            if cfg.get("enable_multimodal_index", True):
                await self._index_multimodal(state, cfg, kb_name, version, channel_id)

            state["processing_stage"] = "finalize"
            return state

    async def _index_vectors(
        self,
        state: IngestState,
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
        cfg: dict[str, Any],
        kb_name: str,
        version: int,
        channel_id: str | None,
        batch_size: int,
    ) -> None:
        """Index text chunks to Qdrant."""
        collection_name = channel_collection_name(channel_id, kb_name, version)
        vector_client = get_vector_client()

        # Ensure collection exists
        dim = cfg.get("embedding_dimensions", 1024)
        quant = cfg.get("enable_quantization", True)
        await vector_client.ensure_collection(
            collection_name, dim=dim, enable_quantization=quant
        )

        # Batch upsert
        for i in range(0, len(chunks), batch_size):
            points = []
            for chunk, vec in zip(
                chunks[i : i + batch_size], vectors[i : i + batch_size], strict=False
            ):
                # Add channel_id to metadata for additional filtering
                metadata = chunk.get("metadata", {})
                if channel_id:
                    metadata["channel_id"] = channel_id
                points.append(
                    PointStruct(
                        id=chunk["id"],
                        vector=vec,
                        payload={
                            "content": chunk["content"],
                            "metadata": metadata,
                            "doc_id": chunk["doc_id"],
                            "chunk_index": chunk["chunk_index"],
                            "channel_id": channel_id,
                        },
                    )
                )
            if not points:
                continue
            try:
                await vector_client.upsert(collection_name, points)
                if "progress" in state:
                    done = state["progress"].get("indexed_vector", 0) + len(points)
                    state["progress"]["indexed_vector"] = done
            except Exception as e:
                state["error_log"].append(
                    {
                        "stage": "indexer",
                        "backend": "vector",
                        "batch_start": i,
                        "error": str(e),
                    }
                )

    async def _index_keywords(
        self,
        state: IngestState,
        chunks: list[dict[str, Any]],
        cfg: dict[str, Any],
        kb_name: str,
        channel_id: str | None,
        batch_size: int,
    ) -> None:
        """Index text chunks to Elasticsearch."""
        index_name = channel_index_name(channel_id, kb_name)
        keyword_client = get_keyword_client()

        await keyword_client.ensure_index(index_name)

        for i in range(0, len(chunks), batch_size):
            es_docs = []
            for chunk in chunks[i : i + batch_size]:
                es_docs.append(
                    {
                        "id": chunk["id"],
                        "content": chunk["content"],
                        "metadata": chunk["metadata"],
                        "doc_id": chunk["doc_id"],
                        "chunk_index": chunk["chunk_index"],
                    }
                )
            if not es_docs:
                continue
            try:
                await keyword_client.bulk_upsert(index_name, es_docs)
                if "progress" in state:
                    done = state["progress"].get("indexed_keyword", 0) + len(es_docs)
                    state["progress"]["indexed_keyword"] = done
            except Exception as e:
                state["error_log"].append(
                    {
                        "stage": "indexer",
                        "backend": "keyword",
                        "batch_start": i,
                        "error": str(e),
                    }
                )

    async def _index_multimodal(
        self,
        state: IngestState,
        cfg: dict[str, Any],
        kb_name: str,
        version: int,
        channel_id: str | None,
    ) -> None:
        """
        Index multimodal content (images, tables) to separate collections.

        Creates:
        - kb_{name}_images: Image embeddings for visual search
        - kb_{name}_tables: Table embeddings with structured metadata
        """
        vector_client = get_vector_client()
        dim = cfg.get("embedding_dimensions", 1024)

        # 1. Index Images
        images = state.get("images", [])
        if images:
            await self._index_images(
                state, images, vector_client, kb_name, version, channel_id, dim
            )

        # 2. Index Tables (separate collection for table-specific queries)
        table_chunks = [
            (c, v)
            for c, v in zip(state["chunks"], state["vectors"], strict=False)
            if c.get("metadata", {}).get("block_type") == "table"
        ]
        if table_chunks:
            await self._index_tables(
                state, table_chunks, vector_client, kb_name, version, channel_id, dim
            )

    async def _index_images(
        self,
        state: IngestState,
        images: list[dict[str, Any]],
        vector_client: Any,
        kb_name: str,
        version: int,
        channel_id: str | None,
        dim: int,
    ) -> None:
        """Index image embeddings to dedicated collection."""
        # Collection name for images
        if channel_id:
            collection_name = f"ch_{channel_id}_kb_{kb_name}_v{version}_images"
        else:
            collection_name = f"kb_{kb_name}_v{version}_images"

        # Ensure image collection exists
        await vector_client.ensure_collection(collection_name, dim=dim, enable_quantization=False)

        # Try to get embedder from capability loader
        embedder = None
        capability_loader = state.get("capability_loader")
        if capability_loader and hasattr(capability_loader, "get"):
            embedder = capability_loader.get("multimodal_embedding")

        if not embedder:
            # No embedder available - skip image indexing
            state["error_log"].append({
                "stage": "indexer",
                "backend": "multimodal",
                "warning": "No multimodal embedder available, skipping image indexing"
            })
            return

        points = []
        for i, img_data in enumerate(images):
            try:
                # Generate image embedding
                img_bytes = img_data.get("data")
                if not img_bytes:
                    continue

                embedding = await embedder.embed_image(img_bytes)
                if not embedding:
                    continue

                point_id = f"{state['task_id']}_img_{i}"
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "doc_id": state["task_id"],
                            "image_index": i,
                            "page": img_data.get("page", 0),
                            "bbox": img_data.get("bbox"),
                            "caption": img_data.get("caption", ""),
                            "channel_id": channel_id,
                        },
                    )
                )
            except Exception as e:
                state["error_log"].append({
                    "stage": "indexer",
                    "backend": "multimodal",
                    "image_index": i,
                    "error": str(e),
                })

        if points:
            try:
                await vector_client.upsert(collection_name, points)
                if "progress" in state:
                    state["progress"]["indexed_images"] = len(points)
            except Exception as e:
                state["error_log"].append({
                    "stage": "indexer",
                    "backend": "multimodal_image",
                    "error": str(e),
                })

    async def _index_tables(
        self,
        state: IngestState,
        table_chunks: list[tuple[dict[str, Any], list[float]]],
        vector_client: Any,
        kb_name: str,
        version: int,
        channel_id: str | None,
        dim: int,
    ) -> None:
        """Index table embeddings to dedicated collection."""
        # Collection name for tables
        if channel_id:
            collection_name = f"ch_{channel_id}_kb_{kb_name}_v{version}_tables"
        else:
            collection_name = f"kb_{kb_name}_v{version}_tables"

        # Ensure table collection exists
        await vector_client.ensure_collection(collection_name, dim=dim, enable_quantization=True)

        points = []
        for chunk, vec in table_chunks:
            metadata = chunk.get("metadata", {})
            points.append(
                PointStruct(
                    id=chunk["id"],
                    vector=vec,
                    payload={
                        "content": chunk["content"],
                        "doc_id": chunk["doc_id"],
                        "chunk_index": chunk["chunk_index"],
                        "page": metadata.get("page_num", 0),
                        "bbox": metadata.get("bbox"),
                        "channel_id": channel_id,
                        "block_type": "table",
                        # Table-specific metadata
                        "row_count": self._estimate_table_rows(chunk["content"]),
                        "column_count": self._estimate_table_cols(chunk["content"]),
                    },
                )
            )

        if points:
            try:
                await vector_client.upsert(collection_name, points)
                if "progress" in state:
                    state["progress"]["indexed_tables"] = len(points)
            except Exception as e:
                state["error_log"].append({
                    "stage": "indexer",
                    "backend": "multimodal_table",
                    "error": str(e),
                })

    def _estimate_table_rows(self, content: str) -> int:
        """Estimate number of rows in markdown table."""
        if not content:
            return 0
        lines = [l for l in content.split("\n") if l.strip().startswith("|")]
        # Subtract header separator line
        return max(0, len(lines) - 1)

    def _estimate_table_cols(self, content: str) -> int:
        """Estimate number of columns in markdown table."""
        if not content:
            return 0
        for line in content.split("\n"):
            if line.strip().startswith("|"):
                return line.count("|") - 1
        return 0

