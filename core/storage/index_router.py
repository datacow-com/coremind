from typing import Tuple, Optional
from core.storage.local_index import get_index as get_local
from core.storage.milvus_store import MilvusStore


_MILVUS_CN: MilvusStore | None = None
_MILVUS_EN: MilvusStore | None = None


def get_backends() -> Tuple[MilvusStore, bool]:
    global _MILVUS_CN, _MILVUS_EN
    if _MILVUS_CN is None:
        _MILVUS_CN = MilvusStore(dim=256, collection_name="omnirag_chunks_cn")
        _MILVUS_CN.try_init()
    if _MILVUS_EN is None:
        _MILVUS_EN = MilvusStore(dim=256, collection_name="omnirag_chunks_en")
        _MILVUS_EN.try_init()
    # 返回一个可用的实例（优先 CN），以及是否至少有一个可用
    primary = _MILVUS_CN if (_MILVUS_CN and _MILVUS_CN.available) else _MILVUS_EN
    ok = bool((_MILVUS_CN and _MILVUS_CN.available) or (_MILVUS_EN and _MILVUS_EN.available))
    return (primary, ok)


def _detect_lang(text: Optional[str]) -> str:
    t = (text or "").strip()
    if not t:
        return "en"
    # 简易中文检测：CJK字符占比
    total = len(t)
    cjk = sum(1 for ch in t if '\u4e00' <= ch <= '\u9fff')
    return "cn" if (total and (cjk / total) >= 0.2) else "en"


def _select_store_by_lang(lang: str) -> Optional[MilvusStore]:
    global _MILVUS_CN, _MILVUS_EN
    if lang == "cn":
        return _MILVUS_CN if (_MILVUS_CN and _MILVUS_CN.available) else _MILVUS_EN
    return _MILVUS_EN if (_MILVUS_EN and _MILVUS_EN.available) else _MILVUS_CN


def add(vec, meta):
    # 根据内容语言选择集合
    lang = _detect_lang(meta.get("content"))
    store = _select_store_by_lang(lang)
    if store is not None and store.available:
        try:
            store.add(vec, meta)
            return
        except Exception:
            pass
    # fallback to local
    idx = get_local()
    idx.add(vec, meta)


def search(qvec, top_k=5, lang_hint: Optional[str] = None):
    # 根据查询语言提示选择集合
    lang = (lang_hint or "").lower()
    if lang not in ("cn", "en"):
        # 无提示时优先 EN（通用），如果不可用则 CN
        lang = "en"
    store = _select_store_by_lang(lang)
    if store is not None and store.available:
        try:
            return store.search(qvec, top_k=top_k)
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


def delete_document(doc_id: str) -> int:
    milvus, ok = get_backends()
    removed = 0
    if ok:
        try:
            removed += milvus.delete_document(doc_id)
        except Exception:
            pass
    idx = get_local()
    removed += idx.delete_document(doc_id)
    return removed


def list_collections_info():
    infos = []
    global _MILVUS_CN, _MILVUS_EN
    for store, name in [(_MILVUS_CN, "omnirag_chunks_cn"), (_MILVUS_EN, "omnirag_chunks_en")]:
        if store is not None and store.available and getattr(store, "collection", None) is not None:
            try:
                chunk_count = int(getattr(store.collection, "num_entities", 0))
            except Exception:
                chunk_count = 0
            infos.append({
                "name": name,
                "document_count": 0,
                "chunk_count": chunk_count,
                "embedding_dimension": store.dim,
                "distance_metric": "COSINE",
            })
    if not infos:
        stats = get_local().stats_all()
        infos.append({
            "name": "local_index",
            "document_count": stats.get("document_count", 0),
            "chunk_count": stats.get("chunk_count", 0),
            "embedding_dimension": stats.get("embedding_dimension", 256),
            "distance_metric": "cosine",
        })
    return infos
