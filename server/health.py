import os

from server.config import settings


def get_health() -> dict[str, bool]:
    status = {
        "app_up": True,
        "milvus_connected": False,
        "postgres_connected": False,
        "supabase_ready": False,
    }
    # Milvus check
    try:
        uri = settings.milvus_uri_resolved
        if uri:
            from pymilvus import connections, utility

            connections.connect(alias="health", uri=uri)
            _ = utility.get_server_version()
            status["milvus_connected"] = True
    except Exception:
        status["milvus_connected"] = False
    # Postgres check
    try:
        if settings.database_url:
            import psycopg2

            conn = psycopg2.connect(settings.database_url)
            conn.close()
            status["postgres_connected"] = True
    except Exception:
        status["postgres_connected"] = False
    # Supabase REST readiness
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        status["supabase_ready"] = True
    return status
