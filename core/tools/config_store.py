import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text


def _db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://omnirag:omnirag_password@postgres:5432/omnirag",
    )


@lru_cache(maxsize=1)
def load_web_search_configs() -> list[dict[str, Any]]:
    """
    从 DB 读取启用的 WebSearchConfig，按 priority, created_at 排序。
    """
    try:
        eng = create_engine(_db_url(), future=True)
        with eng.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "select * from web_search_configs where enabled = true order by is_default desc, priority desc, created_at asc"
                    )
                )
                .mappings()
                .all()
            )
            return [dict(r) for r in rows] if rows else []
    except Exception:
        return []
