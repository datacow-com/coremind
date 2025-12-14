"""Shared fixtures and strategies for performance tests.

Provides pytest fixtures for performance testing utilities
and hypothesis strategies for property-based testing.
"""

import pytest
from hypothesis import strategies as st

from tests.core.performance.utils.fake_blob_store import FakeBlobStore
from tests.core.performance.utils.memory_tracker import MemoryTracker
from tests.core.performance.utils.metrics_collector import MetricsCollector


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def fake_blob_store() -> FakeBlobStore:
    """Create a FakeBlobStore with default settings."""
    return FakeBlobStore()


@pytest.fixture
def fake_blob_store_100mb() -> FakeBlobStore:
    """Create a FakeBlobStore for 100MB file."""
    return FakeBlobStore(file_size=100 * 1024 * 1024)


@pytest.fixture
def fake_blob_store_500mb() -> FakeBlobStore:
    """Create a FakeBlobStore for 500MB file."""
    return FakeBlobStore(file_size=500 * 1024 * 1024)


@pytest.fixture
def fake_blob_store_no_streaming() -> FakeBlobStore:
    """Create a FakeBlobStore without streaming support."""
    return FakeBlobStore(
        file_size=200 * 1024 * 1024,
        supports_streaming=False,
    )


@pytest.fixture
def memory_tracker() -> MemoryTracker:
    """Create a MemoryTracker instance."""
    tracker = MemoryTracker()
    yield tracker
    # Ensure tracker is stopped after test
    if tracker._tracking:
        tracker.stop()


@pytest.fixture
def metrics_collector() -> MetricsCollector:
    """Create a MetricsCollector instance."""
    return MetricsCollector()


# =============================================================================
# Hypothesis Strategies
# =============================================================================


# File size strategies
file_size_small = st.integers(
    min_value=1024,  # 1KB
    max_value=10 * 1024 * 1024,  # 10MB
)

file_size_large = st.integers(
    min_value=100 * 1024 * 1024,  # 100MB
    max_value=500 * 1024 * 1024,  # 500MB
)

file_size_medium = st.integers(
    min_value=10 * 1024 * 1024,  # 10MB
    max_value=100 * 1024 * 1024,  # 100MB
)

# Chunk size strategies
chunk_size = st.integers(
    min_value=1024,  # 1KB
    max_value=1024 * 1024,  # 1MB
)

# Concurrency level strategies
concurrency_level = st.integers(min_value=1, max_value=20)

semaphore_limit = st.integers(min_value=1, max_value=10)

# Cache-related strategies
cache_hit_rate = st.floats(min_value=0.0, max_value=1.0)

cache_size = st.integers(min_value=100, max_value=10000)

# Request count strategies
request_count = st.integers(min_value=10, max_value=100)

# Document count strategies
document_count = st.integers(min_value=10, max_value=200)

# Latency strategies (in seconds)
latency_s = st.floats(min_value=0.001, max_value=1.0)


# =============================================================================
# Composite Strategies
# =============================================================================


@st.composite
def fake_blob_store_config(draw):
    """Generate FakeBlobStore configuration."""
    return {
        "file_size": draw(file_size_large),
        "chunk_size": draw(chunk_size),
        "supports_streaming": draw(st.booleans()),
    }


@st.composite
def concurrency_test_config(draw):
    """Generate concurrency test configuration."""
    sem_limit = draw(semaphore_limit)
    num_requests = draw(st.integers(min_value=sem_limit + 1, max_value=sem_limit * 5))
    return {
        "semaphore_limit": sem_limit,
        "num_requests": num_requests,
    }


@st.composite
def cache_test_config(draw):
    """Generate cache test configuration."""
    return {
        "cache_size": draw(cache_size),
        "hit_rate": draw(cache_hit_rate),
        "num_requests": draw(request_count),
    }


# =============================================================================
# Performance Test Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "memory_intensive: mark test as memory intensive"
    )
