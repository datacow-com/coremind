import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator
from .models import Base

# Database configuration
_RAW_DB_URL = os.getenv("DATABASE_URL", "postgresql://omnirag:omnirag_password@localhost:5432/omnirag")
_ASYNC_DB_URL = _RAW_DB_URL if "+asyncpg" in _RAW_DB_URL else _RAW_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
DATABASE_URL = _ASYNC_DB_URL

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Create sync engine for migrations
sync_engine = create_engine(
    _RAW_DB_URL,
    echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync():
    """Initialize database tables synchronously"""
    Base.metadata.create_all(bind=sync_engine)
