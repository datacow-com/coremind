"""
Real environment test fixtures for E2E testing.

Provides fixtures for connecting to real docker-compose services:
- Qdrant (port 3508)
- Elasticsearch (port 3507)
- MinIO (port 3510)
- Redis (port 3509)

These fixtures skip tests if services are unavailable.
"""

import os
import socket
import uuid
from pathlib import Path
from typing import Generator

import pytest


# =============================================================================
# Service Availability Checks
# =============================================================================


def is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def check_qdrant_available() -> bool:
    """Check if Qdrant is available."""
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "3508"))
    return is_port_open(host, port)


def check_elasticsearch_available() -> bool:
    """Check if Elasticsearch is available."""
    host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
    port = int(os.environ.get("ELASTICSEARCH_PORT", "3507"))
    return is_port_open(host, port)


def check_minio_available() -> bool:
    """Check if MinIO is available."""
    host = os.environ.get("MINIO_HOST", "localhost")
    port = int(os.environ.get("MINIO_PORT", "3510"))
    return is_port_open(host, port)


def check_redis_available() -> bool:
    """Check if Redis is available."""
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "3509"))
    return is_port_open(host, port)


# =============================================================================
# Pytest Markers
# =============================================================================

# Skip markers for unavailable services
requires_qdrant = pytest.mark.skipif(
    not check_qdrant_available(),
    reason="Qdrant not available. Run: docker-compose up -d qdrant"
)

requires_elasticsearch = pytest.mark.skipif(
    not check_elasticsearch_available(),
    reason="Elasticsearch not available. Run: docker-compose up -d elasticsearch"
)

requires_minio = pytest.mark.skipif(
    not check_minio_available(),
    reason="MinIO not available. Run: docker-compose up -d minio"
)

requires_redis = pytest.mark.skipif(
    not check_redis_available(),
    reason="Redis not available. Run: docker-compose up -d redis"
)

requires_all_services = pytest.mark.skipif(
    not all([
        check_qdrant_available(),
        check_elasticsearch_available(),
        check_minio_available(),
        check_redis_available(),
    ]),
    reason="Not all services available. Run: docker-compose up -d"
)


# =============================================================================
# Real Service Client Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def real_qdrant_client():
    """
    Real Qdrant client connected to docker-compose service.
    
    Skips tests if Qdrant is not available.
    """
    if not check_qdrant_available():
        pytest.skip("Qdrant not available. Run: docker-compose up -d qdrant")
    
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        pytest.skip("qdrant-client package not installed. Run: pip install qdrant-client")
    
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "3508"))
    
    client = QdrantClient(host=host, port=port)
    
    # Verify connection
    try:
        client.get_collections()
    except Exception as e:
        pytest.skip(f"Cannot connect to Qdrant: {e}")
    
    yield client


@pytest.fixture(scope="session")
def real_es_client():
    """
    Real Elasticsearch client connected to docker-compose service.
    
    Skips tests if Elasticsearch is not available.
    """
    if not check_elasticsearch_available():
        pytest.skip("Elasticsearch not available. Run: docker-compose up -d elasticsearch")
    
    try:
        from elasticsearch import Elasticsearch
        import elasticsearch
    except ImportError:
        pytest.skip("elasticsearch package not installed. Run: pip install elasticsearch")
    
    host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
    port = int(os.environ.get("ELASTICSEARCH_PORT", "3507"))
    url = os.environ.get("ELASTICSEARCH_URL", f"http://{host}:{port}")
    
    # Check ES client version and configure accordingly
    es_version = tuple(int(x) for x in elasticsearch.__version__[:3])
    
    if es_version[0] >= 9:
        # ES client 9.x requires compatible_with parameter for ES 8.x server
        # But this doesn't work well, so we use basic connection and skip ping
        client = Elasticsearch(hosts=[url])
        # Verify connection using httpx instead of ES client methods
        try:
            import httpx
            resp = httpx.get(f"{url}/_cluster/health", timeout=5.0)
            if resp.status_code != 200:
                pytest.skip(f"Elasticsearch health check failed: {resp.status_code}")
        except Exception as e:
            pytest.skip(f"Cannot connect to Elasticsearch: {e}")
    else:
        # ES client 8.x works directly with ES 8.x server
        client = Elasticsearch(hosts=[url])
        try:
            if not client.ping():
                pytest.skip("Elasticsearch ping failed")
        except Exception as e:
            pytest.skip(f"Cannot connect to Elasticsearch: {e}")
    
    yield client


@pytest.fixture(scope="session")
def real_minio_client():
    """
    Real MinIO client connected to docker-compose service.
    
    Skips tests if MinIO is not available.
    """
    if not check_minio_available():
        pytest.skip("MinIO not available. Run: docker-compose up -d minio")
    
    try:
        from minio import Minio
    except ImportError:
        pytest.skip("minio package not installed. Run: pip install minio")
    
    host = os.environ.get("MINIO_HOST", "localhost")
    port = int(os.environ.get("MINIO_PORT", "3510"))
    endpoint = f"{host}:{port}"
    access_key = os.environ.get("MINIO_ROOT_USER", "minioadmin")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin")
    
    client = Minio(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )
    
    # Verify connection
    try:
        client.list_buckets()
    except Exception as e:
        pytest.skip(f"Cannot connect to MinIO: {e}")
    
    yield client


@pytest.fixture(scope="session")
def real_redis_client():
    """
    Real Redis client connected to docker-compose service.
    
    Skips tests if Redis is not available.
    """
    if not check_redis_available():
        pytest.skip("Redis not available. Run: docker-compose up -d redis")
    
    try:
        import redis
    except ImportError:
        pytest.skip("redis package not installed. Run: pip install redis")
    
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "3509"))
    
    client = redis.Redis(host=host, port=port, decode_responses=True)
    
    # Verify connection
    try:
        client.ping()
    except Exception as e:
        pytest.skip(f"Cannot connect to Redis: {e}")
    
    yield client


# =============================================================================
# Channel ID Generators for Test Isolation
# =============================================================================


@pytest.fixture(scope="function")
def test_channel_a() -> str:
    """
    Generate unique channel_id for test isolation (channel A).
    
    Each test gets a unique channel to prevent cross-test interference.
    """
    return f"test_channel_a_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def test_channel_b() -> str:
    """
    Generate unique channel_id for cross-tenant testing (channel B).
    
    Used alongside test_channel_a for multi-tenant isolation tests.
    """
    return f"test_channel_b_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def unique_channel_id() -> str:
    """
    Generate a single unique channel_id for simple tests.
    """
    return f"test_ch_{uuid.uuid4().hex[:8]}"


# =============================================================================
# Test Document Paths
# =============================================================================


@pytest.fixture(scope="session")
def test_docs_dir() -> Path:
    """Path to test documents directory."""
    return Path(__file__).parent / "docs"


@pytest.fixture(scope="session")
def large_pdf_path(test_docs_dir: Path) -> Path:
    """Path to large PDF for lazy loading tests."""
    path = test_docs_dir / "地方导游基础知识.pdf"
    if not path.exists():
        pytest.skip(f"Test document not found: {path}")
    return path


@pytest.fixture(scope="session")
def mixed_content_pdf_path(test_docs_dir: Path) -> Path:
    """Path to PDF with mixed tables and images."""
    path = test_docs_dir / "2010_图说十二月花神.pdf"
    if not path.exists():
        pytest.skip(f"Test document not found: {path}")
    return path


@pytest.fixture(scope="session")
def table_pdf_path(test_docs_dir: Path) -> Path:
    """Path to PDF with tables for layout_aware testing."""
    path = test_docs_dir / "Slang Rules A Practical Guide for English Learners (Merriam Webster Learners) ( etc.)-1c9820566d4e.pdf"
    if not path.exists():
        pytest.skip(f"Test document not found: {path}")
    return path


@pytest.fixture(scope="session")
def pptx_path(test_docs_dir: Path) -> Path:
    """Path to PPTX for multimedia parsing tests."""
    path = test_docs_dir / "儿童节76.pptx"
    if not path.exists():
        pytest.skip(f"Test document not found: {path}")
    return path


# =============================================================================
# Temp Directory Fixture
# =============================================================================


@pytest.fixture(scope="session")
def uploads_tmp_dir() -> Path:
    """Path to uploads/tmp directory for cleanup verification."""
    return Path("uploads/tmp")



# =============================================================================
# Resource Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=False)
def cleanup_qdrant_collections(
    real_qdrant_client,
    test_channel_a: str,
    test_channel_b: str,
) -> Generator[None, None, None]:
    """
    Cleanup Qdrant collections created during tests.
    
    Deletes all collections prefixed with test channel IDs after test completion.
    """
    yield
    
    # Cleanup collections for both test channels
    try:
        collections = real_qdrant_client.get_collections().collections
        for col in collections:
            if col.name.startswith(f"ch_{test_channel_a}") or \
               col.name.startswith(f"ch_{test_channel_b}"):
                try:
                    real_qdrant_client.delete_collection(col.name)
                except Exception:
                    pass  # Ignore cleanup errors
    except Exception:
        pass  # Service may be unavailable


@pytest.fixture(autouse=False)
def cleanup_es_indexes(
    real_es_client,
    test_channel_a: str,
    test_channel_b: str,
) -> Generator[None, None, None]:
    """
    Cleanup Elasticsearch indexes created during tests.
    
    Deletes all indexes prefixed with test channel IDs after test completion.
    """
    yield
    
    # Cleanup indexes for both test channels
    try:
        for channel in [test_channel_a, test_channel_b]:
            pattern = f"ch_{channel}_*"
            try:
                real_es_client.indices.delete(index=pattern, ignore_unavailable=True)
            except Exception:
                pass  # Ignore cleanup errors
    except Exception:
        pass  # Service may be unavailable


@pytest.fixture(autouse=False)
def cleanup_minio_objects(
    real_minio_client,
    test_channel_a: str,
    test_channel_b: str,
) -> Generator[None, None, None]:
    """
    Cleanup MinIO objects created during tests.
    
    Deletes all objects under test channel prefixes after test completion.
    """
    yield
    
    bucket_name = os.environ.get("MINIO_BUCKET", "omnirag")
    
    try:
        # Check if bucket exists
        if not real_minio_client.bucket_exists(bucket_name):
            return
        
        for channel in [test_channel_a, test_channel_b]:
            prefix = f"channels/{channel}/"
            try:
                objects = real_minio_client.list_objects(
                    bucket_name, prefix=prefix, recursive=True
                )
                for obj in objects:
                    real_minio_client.remove_object(bucket_name, obj.object_name)
            except Exception:
                pass  # Ignore cleanup errors
    except Exception:
        pass  # Service may be unavailable


@pytest.fixture(autouse=False)
def cleanup_redis_keys(
    real_redis_client,
    test_channel_a: str,
    test_channel_b: str,
) -> Generator[None, None, None]:
    """
    Cleanup Redis keys created during tests.
    
    Deletes all keys prefixed with test channel IDs after test completion.
    """
    yield
    
    try:
        for channel in [test_channel_a, test_channel_b]:
            pattern = f"*{channel}*"
            try:
                keys = real_redis_client.keys(pattern)
                if keys:
                    real_redis_client.delete(*keys)
            except Exception:
                pass  # Ignore cleanup errors
    except Exception:
        pass  # Service may be unavailable


@pytest.fixture(autouse=False)
def cleanup_temp_files(uploads_tmp_dir: Path) -> Generator[None, None, None]:
    """
    Cleanup temporary files in uploads/tmp directory.
    
    Removes all files from the temp directory after test completion.
    """
    yield
    
    try:
        if uploads_tmp_dir.exists():
            for f in uploads_tmp_dir.glob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        import shutil
                        shutil.rmtree(f)
                except Exception:
                    pass  # Ignore cleanup errors
    except Exception:
        pass


@pytest.fixture(autouse=False)
def cleanup_all_resources(
    cleanup_qdrant_collections,
    cleanup_es_indexes,
    cleanup_minio_objects,
    cleanup_redis_keys,
    cleanup_temp_files,
) -> Generator[None, None, None]:
    """
    Combined cleanup fixture for all resources.
    
    Use this fixture when a test needs to clean up all resource types.
    """
    yield


# =============================================================================
# Test Execution State Tracking
# =============================================================================


@pytest.fixture(scope="function")
def test_execution_state(
    test_channel_a: str,
    test_channel_b: str,
) -> dict:
    """
    Track resources created during test execution.
    
    Useful for debugging and manual cleanup if needed.
    """
    import time
    import psutil
    
    return {
        "channel_a": test_channel_a,
        "channel_b": test_channel_b,
        "created_collections": [],
        "created_indexes": [],
        "uploaded_objects": [],
        "temp_files": [],
        "start_time": time.time(),
        "memory_baseline": psutil.Process().memory_info().rss,
    }


# =============================================================================
# Database and Storage Reset Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset database engine and storage singletons before and after each test.
    
    This prevents:
    1. "Event loop is closed" errors when using asyncpg across different event loops
    2. "Event loop is closed" errors when using aiohttp (Elasticsearch client)
    3. Prometheus metrics duplicate registration errors
    """
    def _reset_all():
        # Reset database engine
        try:
            from server.database import reset_engine_force
            reset_engine_force()
        except ImportError:
            pass
        
        # Reset vector store (Qdrant)
        try:
            from core.storage.vector_store import reset_vector_client
            reset_vector_client()
        except ImportError:
            pass
        
        # Reset keyword store (Elasticsearch) - critical for aiohttp session
        try:
            from core.storage.keyword_store import reset_keyword_client
            reset_keyword_client()
        except ImportError:
            pass
    
    # Reset before test
    _reset_all()
    
    yield
    
    # Reset after test
    _reset_all()


# =============================================================================
# GPU Availability Check
# =============================================================================


def check_gpu_available() -> bool:
    """Check if GPU (CUDA) is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


requires_gpu = pytest.mark.skipif(
    not check_gpu_available(),
    reason="GPU not available"
)


skip_if_no_gpu = pytest.mark.skipif(
    not check_gpu_available(),
    reason="GPU not available - skipping GPU-specific test"
)


# =============================================================================
# Network Availability Check
# =============================================================================


def check_external_network_available() -> bool:
    """Check if external network is available for web search tests."""
    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            response = client.get("https://duckduckgo.com")
            return response.status_code == 200
    except Exception:
        return False


requires_external_network = pytest.mark.skipif(
    not check_external_network_available(),
    reason="External network not available"
)
