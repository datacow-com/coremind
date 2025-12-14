"""
Global pytest configuration for core tests.

This file provides fixtures and configuration that apply to all tests
in the tests/core directory.

Key features:
1. Database engine reset between tests to avoid event loop issues
2. Proper async fixture scoping
3. Global cleanup hooks
"""

import asyncio
import pytest
from typing import Generator


# =============================================================================
# Event Loop Configuration
# =============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# =============================================================================
# Database Engine Reset Fixture
# =============================================================================

@pytest.fixture(autouse=True)
async def reset_global_state():
    """
    Reset global state before and after each test.
    
    This is critical for async tests that use SQLAlchemy/asyncpg because:
    1. The database engine is a global singleton
    2. asyncpg connections are bound to a specific event loop
    3. pytest-asyncio creates a new event loop for each test
    
    Without this reset, connections from previous tests will fail with
    "Event loop is closed" or "Future attached to a different loop" errors.
    """
    # Reset before test
    await _reset_all_global_state()
    
    yield
    
    # Reset after test
    await _reset_all_global_state()


async def _reset_all_global_state():
    """Reset all global singleton state that may hold event loop references."""
    # Reset database engine
    try:
        from server.database import reset_engine
        await reset_engine()
    except (ImportError, Exception):
        pass
    
    # Reset vector store client
    try:
        from core.storage.vector_store import _VECTOR_STORE
        import core.storage.vector_store as vs_module
        vs_module._VECTOR_STORE = None
    except (ImportError, Exception):
        pass
    
    # Reset blob store client
    try:
        import core.storage.blob_store as bs_module
        if hasattr(bs_module, '_BLOB_STORE'):
            bs_module._BLOB_STORE = None
    except (ImportError, Exception):
        pass
    
    # Reset checkpoint saver
    try:
        from core.storage.checkpoint import cleanup_postgres_saver
        cleanup_postgres_saver()
    except (ImportError, Exception):
        pass


# =============================================================================
# Test Isolation Helpers
# =============================================================================

@pytest.fixture(scope="function")
def isolated_test_env() -> Generator[dict, None, None]:
    """
    Provide an isolated test environment with unique identifiers.
    
    This fixture ensures each test has unique channel IDs and task IDs
    to prevent cross-test interference.
    """
    import uuid
    
    env = {
        "channel_id": f"test_ch_{uuid.uuid4().hex[:8]}",
        "task_id": f"test_task_{uuid.uuid4().hex[:8]}",
        "batch_id": f"test_batch_{uuid.uuid4().hex[:8]}",
    }
    
    yield env


# =============================================================================
# Async Test Helpers
# =============================================================================

@pytest.fixture
def anyio_backend():
    """Specify the async backend for anyio-based tests."""
    return "asyncio"
