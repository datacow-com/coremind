"""
Checkpoint persistence for LangGraph.
Optional - returns None if PostgreSQL is not configured.
"""

import os
from typing import Any

_SAVER: Any = None
_POOL: Any = None
_PostgresSaver: Any = None

# Try to import LangGraph postgres saver
try:
    from langgraph.checkpoint.postgres import PostgresSaver as _PostgresSaver
except ImportError:
    try:
        from langgraph.checkpoint.postgres import AsyncPostgresSaver as _PostgresSaver
    except ImportError:
        _PostgresSaver = None


def get_postgres_saver() -> Any | None:
    """
    Get or create a PostgreSQL checkpointer.
    Returns None if not configured or unavailable.
    """
    global _SAVER

    if _PostgresSaver is None:
        return None

    if _SAVER is not None:
        return _SAVER

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None

    try:
        _SAVER = _PostgresSaver.from_conn_string(db_url)
        return _SAVER
    except Exception:
        return None


async def init_checkpointer():
    """Initialize the checkpointer (setup tables)."""
    saver = get_postgres_saver()
    if saver and hasattr(saver, "setup"):
        await saver.setup()
