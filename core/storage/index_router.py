from typing import Any

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


def list_page_meta(doc_id: str, page_num: int) -> list[dict[str, Any]]:
    return []


def doc_stats(doc_id: str) -> dict[str, Any]:
    return {}


def delete_document(doc_id: str) -> int:
    q_client = get_vector_client()
    try:
        return q_client.delete_document(doc_id)
    except Exception:
        return 0


def list_collections_info() -> list[dict[str, Any]]:
    return []
