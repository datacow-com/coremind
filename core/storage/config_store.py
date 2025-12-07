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
def load_storage_config() -> dict[str, Any]:
    """
    从 DB 读取活跃的存储配置（storage_configs），若失败则返回空 dict，调用方使用 env/settings 兜底。
    """
    try:
        eng = create_engine(_db_url(), future=True)
        with eng.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "select * from storage_configs where is_active = true order by created_at desc limit 1"
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else {}
    except Exception:
        return {}
