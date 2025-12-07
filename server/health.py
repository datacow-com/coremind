import os

from server.config import settings


def get_health() -> dict[str, bool]:
    status = {
        "app_up": True,
        "postgres_connected": False,
        "qdrant_connected": False,
        "es_connected": False,
        "blob_available": False,
    }
    # Postgres check
    try:
        from sqlalchemy import create_engine

        db_url = os.environ.get("DATABASE_URL") or getattr(settings, "database_url", None)
        if db_url:
            eng = create_engine(db_url, future=True)
            with eng.connect() as conn:
                conn.execute("select 1")
            status["postgres_connected"] = True
    except Exception:
        status["postgres_connected"] = False
    # Qdrant
    try:
        from core.storage.vector_store import get_vector_client

        vc = get_vector_client()
        status["qdrant_connected"] = bool(vc.available)
    except Exception:
        status["qdrant_connected"] = False
    # Elasticsearch keyword
    try:
        from core.storage.keyword_store import get_keyword_client

        kc = get_keyword_client()
        status["es_connected"] = bool(kc.available)
    except Exception:
        status["es_connected"] = False
    # Blob
    try:
        from core.storage.blob_store import get_blob_store

        bs = get_blob_store()
        status["blob_available"] = bool(bs)
    except Exception:
        status["blob_available"] = False
    return status
