from typing import Tuple
from core.storage.local_index import get_index as get_local
from core.storage.milvus_store import MilvusStore


_MILVUS = None


def get_backends() -> Tuple[object, bool]:
    global _MILVUS
    if _MILVUS is None:
        _MILVUS = MilvusStore(dim=256, collection_name="omnirag_chunks")
        _MILVUS.try_init()
    return (_MILVUS, bool(_MILVUS and _MILVUS.available))


def add(vec, meta):
    milvus, ok = get_backends()
    if ok:
        try:
            milvus.add(vec, meta)
            return
        except Exception:
            pass
    # fallback to local
    idx = get_local()
    idx.add(vec, meta)


def search(qvec, top_k=5):
    milvus, ok = get_backends()
    if ok:
        try:
            return milvus.search(qvec, top_k=top_k)
        except Exception:
            pass
    idx = get_local()
    return idx.search(qvec, top_k=top_k)


def list_page_meta(doc_id: str, page_num: int):
    # always use local index for metadata-based listing
    idx = get_local()
    return idx.list_page_meta(doc_id, page_num)


def doc_stats(doc_id: str):
    idx = get_local()
    return idx.doc_stats(doc_id)
