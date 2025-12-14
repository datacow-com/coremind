import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text


def _db_url() -> str:
    # Use docker-compose mapped port for local dev (3504 -> 5432)
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://omnirag:omnirag_password@localhost:3504/omnirag",
    )


@lru_cache(maxsize=1)
def load_storage_config() -> dict[str, Any]:
    """
    从 DB 读取活跃的存储配置（storage_configs），若失败则返回空 dict，调用方使用 env/settings 兜底。
    
    Note: Uses short timeout to avoid blocking on import when DB is unavailable.
    """
    try:
        # Short connect timeout to fail fast if DB unavailable
        eng = create_engine(
            _db_url(), 
            future=True,
            connect_args={"connect_timeout": 3},  # 3 second timeout
        )
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
