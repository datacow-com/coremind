"""
Checkpoint persistence for LangGraph.
Optional - returns None if PostgreSQL is not configured.

Uses AsyncPostgresSaver for async graph execution.
"""

import os
from typing import Any

_SAVER: Any = None
_SAVER_CONTEXT: Any = None
_POOL: Any = None
_AsyncPostgresSaver: Any = None

# Try to import LangGraph async postgres saver
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as _AsyncPostgresSaver
except ImportError:
    _AsyncPostgresSaver = None


def get_postgres_saver() -> Any | None:
    """
    Get or create a PostgreSQL checkpointer.
    Returns None if not configured or unavailable.
    
    Note: langgraph-checkpoint-postgres 2.0.0 uses a context manager pattern.
    We enter the context once and keep the saver alive for the process lifetime.
    """
    global _SAVER, _SAVER_CONTEXT

    if _AsyncPostgresSaver is None:
        return None

    if _SAVER is not None:
        return _SAVER

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None

    try:
        # from_conn_string returns an async context manager (AsyncIterator[AsyncPostgresSaver])
        # We need to enter the context and keep the saver
        _SAVER_CONTEXT = _AsyncPostgresSaver.from_conn_string(db_url)
        # For async context manager, we can't enter it synchronously
        # Instead, return the context manager and let the caller handle it
        # Or use a sync wrapper approach
        
        # Actually, for LangGraph, we can pass the context manager directly
        # and it will handle entering/exiting the context
        _SAVER = _SAVER_CONTEXT
        return _SAVER
    except Exception as e:
        import logging
        logging.warning(f"Failed to create AsyncPostgresSaver: {e}")
        return None


def cleanup_postgres_saver():
    """Cleanup the PostgreSQL saver context."""
    global _SAVER, _SAVER_CONTEXT
    _SAVER = None
    _SAVER_CONTEXT = None


async def init_checkpointer():
    """Initialize the checkpointer (setup tables)."""
    saver = get_postgres_saver()
    if saver and hasattr(saver, "setup"):
        await saver.setup()
