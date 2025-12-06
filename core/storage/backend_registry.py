from typing import Any

from core.storage.es_store import ElasticsearchStore
from core.storage.local_index import get_index as _get_local
from core.storage.milvus_store import MilvusStore
from core.storage.qdrant_store import QdrantStore
from server.config import settings


def detect_milvus() -> bool:
    try:
        s = MilvusStore(dim=256, collection_name="omnirag_chunks_en")
        ok = s.try_init()
        return bool(ok and s.available)
    except Exception:
        return False


def detect_elasticsearch() -> bool:
    try:
        s = ElasticsearchStore(
            dim=256, index_name=getattr(settings, "elasticsearch_index", None) or "omnirag_chunks"
        )
        ok = s.try_init()
        return bool(ok and s.available)
    except Exception:
        return False


def detect_qdrant() -> bool:
    try:
        s = QdrantStore(
            dim=256,
            collection_name=getattr(settings, "qdrant_collection", None) or "omnirag_chunks",
        )
        ok = s.try_init()
        return bool(ok and s.available)
    except Exception:
        return False


def list_vector_backends() -> dict[str, dict[str, Any]]:
    milvus_ok = detect_milvus()
    es_ok = detect_elasticsearch()
    qdrant_ok = detect_qdrant()
    current = getattr(settings, "vector_backend", None) or "auto"
    return {
        "current": current,
        "backends": {
            "auto": {"available": True},
            "milvus": {"available": milvus_ok},
            "local": {"available": True},
            "elasticsearch": {"available": es_ok},
            "qdrant": {"available": qdrant_ok},
            "weaviate": {"available": False},
        },
    }


def select_vector_backend(name: str) -> dict[str, Any]:
    name = (name or "").lower()
    if name not in {"auto", "milvus", "local", "elasticsearch", "qdrant", "weaviate"}:
        return {"ok": False, "error": "invalid_backend"}
    try:
        settings.vector_backend = name
        return {"ok": True, "current": name}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_vector_store(
    lang: str | None = None,
    collection_name: str | None = None,
    backend_override: str | None = None,
):
    forced = getattr(settings, "force_vector_backend", None)
    backend = (
        backend_override or forced or getattr(settings, "vector_backend", None) or "auto"
    ).lower()
    if backend == "elasticsearch" or (backend == "auto" and detect_elasticsearch()):
        idx_name = (
            collection_name or getattr(settings, "elasticsearch_index", None) or "omnirag_chunks"
        )
        s = ElasticsearchStore(dim=256, index_name=idx_name)
        s.try_init()
        return s
    if backend == "qdrant" or (backend == "auto" and detect_qdrant()):
        cname = collection_name or getattr(settings, "qdrant_collection", None) or "omnirag_chunks"
        s = QdrantStore(dim=256, collection_name=cname)
        s.try_init()
        return s
    if backend == "milvus" or (backend == "auto" and detect_milvus()):
        cn = MilvusStore(dim=256, collection_name="omnirag_chunks_cn")
        en = MilvusStore(dim=256, collection_name="omnirag_chunks_en")
        cn.try_init()
        en.try_init()
        if collection_name:
            c = MilvusStore(dim=256, collection_name=collection_name)
            c.try_init()
            return c if c.available else (cn if cn.available else en)
        if (lang or "en").lower() == "cn":
            return cn if cn.available else en
        return en if en.available else cn
    return _get_local()
