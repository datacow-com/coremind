import os
from typing import AsyncIterator, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple
from langgraph.checkpoint.postgres import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

_SAVER: Optional[AsyncPostgresSaver] = None
_POOL: Optional[AsyncConnectionPool] = None

def get_postgres_saver() -> AsyncPostgresSaver:
    global _SAVER, _POOL
    if _SAVER:
        return _SAVER
    
    db_url = os.environ.get("DATABASE_URL", "postgresql://omnirag:omnirag_password@postgres:5432/omnirag")
    
    # LangGraph AsyncPostgresSaver needs a connection pool or conn string.
    # Recommended pattern is to pass pool.
    if _POOL is None:
        _POOL = AsyncConnectionPool(conninfo=db_url, max_size=20)
        
    _SAVER = AsyncPostgresSaver(_POOL)
    # Ensure table exists is async, usually needs to be awaited on app startup
    # For now we return the saver, setup should be called explicitly
    return _SAVER

async def init_checkpointer():
    saver = get_postgres_saver()
    await saver.setup()

