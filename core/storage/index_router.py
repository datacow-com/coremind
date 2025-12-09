"""
Index Router - Unified interface for vector and keyword storage operations.

Provides high-level functions for document indexing, searching, and metadata management.
"""

from typing import Any

from core.storage.channel_utils import channel_collection_name
from core.storage.keyword_store import get_keyword_client
from core.storage.vector_store import get_vector_client


def add(vec: Any, meta: dict[str, Any]) -> None:
    """Sync add to vector + keyword stores (Qdrant + ES)."""
    q_client = get_vector_client()
    if q_client.available:
        q_client.add(vec, meta)
    k_client = get_keyword_client()
    if k_client.available:
        k_client.legacy_add(vec, meta)


def search(
    qvec: Any,
    top_k: int = 5,
    lang_hint: str | None = None,
    collection_name: str | None = None,
    backend_override: str | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Vector search via Qdrant; keyword handled separately."""
    q_client = get_vector_client()
    if not q_client.available:
        return []
    col = collection_name or "omnirag_chunks"
    return q_client.legacy_search(qvec, top_k=top_k, collection_name=col)


def list_page_meta(
    doc_id: str, page_num: int, kb_name: str | None = None, channel_id: str | None = None
) -> list[dict[str, Any]]:
    """
    List all chunk metadata for a specific page of a document.

    Args:
        doc_id: Document identifier
        page_num: Page number (1-indexed)
        kb_name: Knowledge base name (optional)
        channel_id: Channel identifier (optional)

    Returns:
        List of chunk metadata dicts
    """
    q_client = get_vector_client()
    if not q_client.available:
        return []

    # Determine collection name
    if kb_name:
        collection_name = channel_collection_name(channel_id, kb_name, 1)
    else:
        collection_name = "omnirag_chunks"

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        filter_conditions = [
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
            FieldCondition(key="metadata.page_num", match=MatchValue(value=page_num)),
        ]

        # Scroll through matching points
        results, _ = q_client.client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(must=filter_conditions),
            limit=100,
            with_payload=True,
        )

        return [
            {
                "id": r.id,
                "content": r.payload.get("content"),
                "metadata": r.payload.get("metadata"),
                "doc_id": r.payload.get("doc_id"),
                "chunk_index": r.payload.get("chunk_index"),
            }
            for r in results
        ]
    except Exception:
        return []


def doc_stats(
    doc_id: str, kb_name: str | None = None, channel_id: str | None = None
) -> dict[str, Any]:
    """
    Get statistics for a document.

    Args:
        doc_id: Document identifier
        kb_name: Knowledge base name (optional)
        channel_id: Channel identifier (optional)

    Returns:
        Dict with chunk_count, page_count, etc.
    """
    q_client = get_vector_client()
    if not q_client.available:
        return {"chunk_count": 0, "page_count": 0, "error": "Vector store unavailable"}

    # Determine collection name
    if kb_name:
        collection_name = channel_collection_name(channel_id, kb_name, 1)
    else:
        collection_name = "omnirag_chunks"

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        filter_condition = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
        )

        # Count points matching the filter
        count_result = q_client.client.count(
            collection_name=collection_name,
            count_filter=filter_condition,
        )

        chunk_count = count_result.count

        # Estimate page count by scrolling through unique page numbers
        page_nums = set()
        offset = None
        while True:
            results, offset = q_client.client.scroll(
                collection_name=collection_name,
                scroll_filter=filter_condition,
                limit=100,
                offset=offset,
                with_payload=["metadata"],
            )
            for r in results:
                page = r.payload.get("metadata", {}).get("page_num")
                if page is not None:
                    page_nums.add(page)
            if offset is None:
                break

        return {
            "chunk_count": chunk_count,
            "page_count": len(page_nums),
            "pages": sorted(page_nums) if page_nums else [],
        }
    except Exception as e:
        return {"chunk_count": 0, "page_count": 0, "error": str(e)}


def delete_document(doc_id: str, kb_name: str | None = None, channel_id: str | None = None) -> int:
    """
    Delete all chunks for a document.

    Args:
        doc_id: Document identifier
        kb_name: Knowledge base name (optional)
        channel_id: Channel identifier (optional)

    Returns:
        Number of deleted items (estimated)
    """
    q_client = get_vector_client()

    # Determine collection name
    if kb_name:
        collection_name = channel_collection_name(channel_id, kb_name, 1)
    else:
        collection_name = "omnirag_chunks"

    try:
        return q_client.delete_document(doc_id, collection_name=collection_name)
    except Exception:
        return 0


def list_all_meta(
    kb_name: str | None = None, channel_id: str | None = None, limit: int = 1000
) -> list[dict[str, Any]]:
    """
    List all metadata from the index.

    Args:
        kb_name: Knowledge base name (optional)
        channel_id: Channel identifier (optional)
        limit: Maximum number of results

    Returns:
        List of metadata dicts
    """
    q_client = get_vector_client()
    if not q_client.available:
        return []

    # Determine collection name
    if kb_name:
        collection_name = channel_collection_name(channel_id, kb_name, 1)
    else:
        collection_name = "omnirag_chunks"

    try:
        results, _ = q_client.client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": r.id,
                "content": r.payload.get("content", "")[:200],  # Truncate for performance
                "metadata": r.payload.get("metadata"),
                "doc_id": r.payload.get("doc_id"),
                "chunk_index": r.payload.get("chunk_index"),
            }
            for r in results
        ]
    except Exception:
        return []


def list_collections_info(channel_id: str | None = None) -> list[dict[str, Any]]:
    """
    List all collections with their info.

    Args:
        channel_id: If provided, filter to collections belonging to this channel

    Returns:
        List of collection info dicts with name, points_count, etc.
    """
    q_client = get_vector_client()
    if not q_client.available:
        return []

    try:
        from core.storage.channel_utils import parse_channel_from_collection

        collections_response = q_client.client.get_collections()
        result = []

        for collection in collections_response.collections:
            name = collection.name

            # Parse channel from collection name
            parsed_channel, kb_name, version = parse_channel_from_collection(name)

            # Filter by channel if specified
            if channel_id is not None:
                if parsed_channel != channel_id:
                    continue

            # Get collection info
            try:
                info = q_client.client.get_collection(name)
                points_count = info.points_count
                vectors_count = info.vectors_count
            except Exception:
                points_count = 0
                vectors_count = 0

            result.append(
                {
                    "name": name,
                    "channel_id": parsed_channel,
                    "kb_name": kb_name,
                    "version": version,
                    "points_count": points_count,
                    "vectors_count": vectors_count,
                }
            )

        return result
    except Exception:
        return []


def get_collection_stats(collection_name: str) -> dict[str, Any]:
    """
    Get detailed stats for a specific collection.

    Args:
        collection_name: The collection to query

    Returns:
        Dict with points_count, vectors_count, indexed_vectors_count, etc.
    """
    q_client = get_vector_client()
    if not q_client.available:
        return {"error": "Vector store unavailable"}

    try:
        info = q_client.client.get_collection(collection_name)
        return {
            "name": collection_name,
            "status": info.status.value if hasattr(info.status, "value") else str(info.status),
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "config": {
                "vector_size": info.config.params.vectors.size
                if hasattr(info.config.params.vectors, "size")
                else None,
                "distance": str(info.config.params.vectors.distance)
                if hasattr(info.config.params.vectors, "distance")
                else None,
            },
        }
    except Exception as e:
        return {"error": str(e)}
