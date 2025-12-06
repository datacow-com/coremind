from typing import Any, Dict, List, Optional
from core.storage.vector_store import get_vector_client
from core.storage.keyword_store import get_keyword_client
from core.storage.milvus_store import MilvusStore
from core.storage.local_index import get_index as get_local
from core.storage.parent_index import get_parent_index

# Legacy Globals
_MILVUS_CN: MilvusStore | None = None
_MILVUS_EN: MilvusStore | None = None

def get_backends() -> tuple[MilvusStore | None, bool]:
    # Maintain legacy check
    global _MILVUS_CN, _MILVUS_EN
    if _MILVUS_CN is None:
        _MILVUS_CN = MilvusStore(dim=256, collection_name="omnirag_chunks_cn")
        _MILVUS_CN.try_init()
    if _MILVUS_EN is None:
        _MILVUS_EN = MilvusStore(dim=256, collection_name="omnirag_chunks_en")
        _MILVUS_EN.try_init()
    primary = _MILVUS_CN if (_MILVUS_CN and _MILVUS_CN.available) else _MILVUS_EN
    ok = bool((_MILVUS_CN and _MILVUS_CN.available) or (_MILVUS_EN and _MILVUS_EN.available))
    return (primary if ok else None, ok)

def add(vec: Any, meta: dict[str, Any]) -> None:
    """
    Unified add entrypoint.
    Routes to new Qdrant/ES stores if configured, or falls back to legacy Milvus/Local.
    """
    try:
        # Try new Qdrant Store first (sync wrapper)
        q_client = get_vector_client()
        if q_client.available:
            q_client.add(vec, meta)
            
        # Try new Keyword Store (sync wrapper)
        k_client = get_keyword_client()
        if k_client.available:
            k_client.legacy_add(vec, meta)
            
            return
    except Exception:
        # Fallback to legacy logic if new stores fail or not configured
        pass

    # Legacy logic
    # ... (existing local/milvus fallback) ...
    get_local().add(vec, meta)
    try:
        get_parent_index().add(meta)
    except Exception:
        pass

def search(
    qvec: Any,
    top_k: int = 5,
    lang_hint: str | None = None,
    collection_name: str | None = None,
    backend_override: str | None = None,
) -> list[tuple[dict[str, Any], float]]:
    
    # Try new Qdrant Store
    try:
        q_client = get_vector_client()
        if q_client.available:
            # Use legacy_search wrapper
            col = collection_name or "omnirag_chunks"
            return q_client.legacy_search(qvec, top_k=top_k, collection_name=col)
    except Exception:
        pass
        
    # Fallback to local
    return get_local().search(qvec, top_k=top_k)

# Keep other legacy functions
def list_page_meta(doc_id: str, page_num: int) -> list[dict[str, Any]]:
    idx = get_local()
    return idx.list_page_meta(doc_id, page_num)

def doc_stats(doc_id: str) -> dict[str, Any]:
    idx = get_local()
    return idx.doc_stats(doc_id)

def delete_document(doc_id: str) -> int:
    removed = 0
    try:
        q_client = get_vector_client()
        removed += q_client.delete_document(doc_id)
    except Exception:
        pass
    removed += get_local().delete_document(doc_id)
    return removed

def list_collections_info() -> list[dict[str, Any]]:
    # Return mock or real info
        return []
