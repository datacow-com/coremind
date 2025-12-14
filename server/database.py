import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import Base

# Database configuration - use docker-compose mapped port for local dev
_RAW_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://omnirag:omnirag_password@localhost:3504/omnirag"
)
_ASYNC_DB_URL = (
    _RAW_DB_URL
    if "+asyncpg" in _RAW_DB_URL
    else _RAW_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
)
DATABASE_URL = _ASYNC_DB_URL

# Lazy initialization to avoid blocking on import (fixes py_compile hang)
_engine: Any = None
_async_session_local: Any = None
_sync_engine: Any = None


async def reset_engine():
    """
    Reset the database engine (useful for tests with different event loops).
    
    This is critical for pytest-asyncio tests because:
    1. Each test gets a new event loop
    2. asyncpg connections are bound to the event loop they were created in
    3. Reusing connections across event loops causes "Event loop is closed" errors
    
    Call this at the start and end of each async test to ensure clean state.
    """
    global _engine, _async_session_local
    if _engine is not None:
        try:
            await _engine.dispose()
        except Exception:
            # Engine may already be in a bad state, just clear the reference
            pass
        _engine = None
        _async_session_local = None


def reset_engine_force():
    """
    Force reset engine references without async dispose.
    
    Use this in pytest fixtures that run synchronously before/after async tests.
    This avoids event loop issues by simply clearing references and letting
    the next test create fresh connections in its own event loop.
    """
    global _engine, _async_session_local
    _engine = None
    _async_session_local = None


def reset_engine_sync():
    """
    Synchronously reset the engine references without disposing.
    
    Use this when you can't await (e.g., in cleanup handlers).
    """
    global _engine, _async_session_local
    _engine = None
    _async_session_local = None


def _get_engine():
    """Lazily create async engine on first use."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine


def _get_async_session_local():
    """Lazily create session factory on first use."""
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_local


def _get_sync_engine():
    """Lazily create sync engine on first use."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            _RAW_DB_URL,
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
        )
    return _sync_engine


# Backward compatible properties
class _LazyEngine:
    """Proxy for lazy engine access."""
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

class _LazySessionLocal:
    """Proxy for lazy session factory access."""
    def __call__(self):
        return _get_async_session_local()()
    def __getattr__(self, name):
        return getattr(_get_async_session_local(), name)

class _LazySyncEngine:
    """Proxy for lazy sync engine access."""
    def __getattr__(self, name):
        return getattr(_get_sync_engine(), name)


engine = _LazyEngine()
AsyncSessionLocal = _LazySessionLocal()  # Note: instance, not call result
sync_engine = _LazySyncEngine()


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Get database session (light mode friendly)"""
    if not os.getenv("DATABASE_URL"):
        yield None
        return
    async with _get_async_session_local()() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync():
    """Initialize database tables synchronously"""
    Base.metadata.create_all(bind=_get_sync_engine())
