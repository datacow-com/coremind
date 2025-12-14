"""
Real environment storage integration tests.

Tests storage layer with real Qdrant and Elasticsearch instances
from docker-compose services.

**Requirements: 3.1-3.6**
"""

import asyncio
import os
import uuid
from typing import Any

import pytest

# Import real fixtures from conftest_real
from tests.core.conftest_real import (
    check_elasticsearch_available,
    check_qdrant_available,
    requires_elasticsearch,
    requires_qdrant,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def unique_channel_id() -> str:
    """Generate unique channel_id for test isolation."""
    return f"test_storage_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def unique_kb_name() -> str:
    """Generate unique kb_name for test isolation."""
    return f"test_kb_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def test_collection_name(unique_channel_id: str, unique_kb_name: str) -> str:
    """Generate test collection name."""
    from core.storage.channel_utils import channel_collection_name
    return channel_collection_name(unique_channel_id, unique_kb_name, 1)


@pytest.fixture(scope="function")
def test_index_name(unique_channel_id: str, unique_kb_name: str) -> str:
    """Generate test index name."""
    from core.storage.channel_utils import channel_index_name
    return channel_index_name(unique_channel_id, unique_kb_name)


# =============================================================================
# Qdrant Client Fixture
# =============================================================================


@pytest.fixture(scope="function")
def qdrant_client():
    """Get Qdrant client for tests."""
    if not check_qdrant_available():
        pytest.skip("Qdrant not available. Run: docker-compose up -d qdrant")
    
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        pytest.skip("qdrant-client package not installed")
    
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "3508"))
    
    client = QdrantClient(host=host, port=port)
    
    try:
        client.get_collections()
    except Exception as e:
        pytest.skip(f"Cannot connect to Qdrant: {e}")
    
    yield client


@pytest.fixture(scope="function")
def es_client():
    """Get Elasticsearch client for tests."""
    if not check_elasticsearch_available():
        pytest.skip("Elasticsearch not available. Run: docker-compose up -d elasticsearch")
    
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        pytest.skip("elasticsearch package not installed")
    
    host = os.environ.get("ELASTICSEARCH_HOST", "localhost")
    port = int(os.environ.get("ELASTICSEARCH_PORT", "3507"))
    url = os.environ.get("ELASTICSEARCH_URL", f"http://{host}:{port}")
    
    client = Elasticsearch(hosts=[url])
    
    try:
        import httpx
        resp = httpx.get(f"{url}/_cluster/health", timeout=5.0)
        if resp.status_code != 200:
            pytest.skip(f"Elasticsearch health check failed: {resp.status_code}")
    except Exception as e:
        pytest.skip(f"Cannot connect to Elasticsearch: {e}")
    
    yield client


# =============================================================================
# Cleanup Fixtures
# =============================================================================


@pytest.fixture(autouse=False)
def cleanup_qdrant_collection(
    qdrant_client,
    test_collection_name: str,
):
    """Cleanup Qdrant collection after test."""
    yield
    
    try:
        collections = qdrant_client.get_collections().collections
        for col in collections:
            if col.name == test_collection_name:
                qdrant_client.delete_collection(col.name)
    except Exception:
        pass


@pytest.fixture(autouse=False)
def cleanup_es_index(
    es_client,
    test_index_name: str,
):
    """Cleanup ES index after test."""
    yield
    
    try:
        es_client.indices.delete(index=test_index_name, ignore_unavailable=True)
    except Exception:
        pass




# =============================================================================
# Test Class: Pagination Stability (Task 6.3)
# =============================================================================


class TestPaginationStability:
    """
    Test pagination stability for storage queries.
    
    **Requirements: 3.2**
    
    WHEN index_router queries with pagination THEN the OmniRAG System
    SHALL return stable results across multiple scroll requests.
    """

    @requires_qdrant
    def test_scroll_pagination_returns_stable_results(
        self,
        qdrant_client,
        test_collection_name: str,
        cleanup_qdrant_collection,
    ):
        """
        Test that scroll pagination returns stable, consistent results.
        
        **Requirements: 3.2**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create collection
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE),
        )
        
        # Insert test points
        num_points = 50
        points = []
        for i in range(num_points):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[float(i % 10) / 10.0] * 128,
                    payload={
                        "content": f"Test content {i}",
                        "doc_id": f"doc_{i}",
                        "chunk_index": i,
                    },
                )
            )
        
        qdrant_client.upsert(
            collection_name=test_collection_name,
            points=points,
            wait=True,
        )
        
        # Scroll through all points in batches
        batch_size = 10
        all_ids_first_pass = []
        offset = None
        
        while True:
            results, offset = qdrant_client.scroll(
                collection_name=test_collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
            )
            
            for r in results:
                all_ids_first_pass.append(str(r.id))
            
            if offset is None:
                break
        
        # Second pass - should get same results
        all_ids_second_pass = []
        offset = None
        
        while True:
            results, offset = qdrant_client.scroll(
                collection_name=test_collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
            )
            
            for r in results:
                all_ids_second_pass.append(str(r.id))
            
            if offset is None:
                break
        
        # Verify stability
        assert len(all_ids_first_pass) == num_points, (
            f"First pass should return {num_points} points, got {len(all_ids_first_pass)}"
        )
        assert len(all_ids_second_pass) == num_points, (
            f"Second pass should return {num_points} points, got {len(all_ids_second_pass)}"
        )
        
        # Results should be identical (same order)
        assert all_ids_first_pass == all_ids_second_pass, (
            "Pagination results should be stable across multiple scroll requests"
        )
        
        # No duplicates
        assert len(set(all_ids_first_pass)) == num_points, (
            "Pagination should not return duplicate results"
        )

    @requires_qdrant
    def test_scroll_pagination_no_duplicates(
        self,
        qdrant_client,
        test_collection_name: str,
        cleanup_qdrant_collection,
    ):
        """
        Test that scroll pagination returns no duplicates.
        
        **Requirements: 3.2**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create collection
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=64, distance=Distance.COSINE),
        )
        
        # Insert test points
        num_points = 100
        points = []
        for i in range(num_points):
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[float(i % 10) / 10.0] * 64,
                    payload={"index": i},
                )
            )
        
        qdrant_client.upsert(
            collection_name=test_collection_name,
            points=points,
            wait=True,
        )
        
        # Scroll with small batch size
        batch_size = 7  # Odd number to test edge cases
        all_ids = []
        offset = None
        
        while True:
            results, offset = qdrant_client.scroll(
                collection_name=test_collection_name,
                limit=batch_size,
                offset=offset,
            )
            
            for r in results:
                all_ids.append(str(r.id))
            
            if offset is None:
                break
        
        # Verify no duplicates
        unique_ids = set(all_ids)
        assert len(unique_ids) == len(all_ids), (
            f"Found {len(all_ids) - len(unique_ids)} duplicate IDs in pagination"
        )
        assert len(all_ids) == num_points


# =============================================================================
# Test Class: Dimension Mismatch Error (Task 6.5)
# =============================================================================


class TestDimensionMismatchError:
    """
    Test dimension mismatch error handling.
    
    **Requirements: 3.4**
    
    WHEN vectors with incorrect dimensions are written to Qdrant
    THEN the OmniRAG System SHALL raise an error and record it in error_log.
    """

    @requires_qdrant
    def test_dimension_mismatch_raises_error(
        self,
        qdrant_client,
        test_collection_name: str,
        cleanup_qdrant_collection,
    ):
        """
        Test that writing vectors with wrong dimensions raises an error.
        
        **Requirements: 3.4**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create collection with 128 dimensions
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE),
        )
        
        # Try to insert vector with wrong dimensions (64 instead of 128)
        wrong_dim_point = PointStruct(
            id=str(uuid.uuid4()),
            vector=[0.1] * 64,  # Wrong dimension
            payload={"content": "test"},
        )
        
        with pytest.raises(Exception) as exc_info:
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=[wrong_dim_point],
                wait=True,
            )
        
        # Verify error message mentions dimension
        error_msg = str(exc_info.value).lower()
        assert "dimension" in error_msg or "size" in error_msg or "vector" in error_msg, (
            f"Error should mention dimension mismatch: {exc_info.value}"
        )

    @requires_qdrant
    def test_dimension_mismatch_larger_vector(
        self,
        qdrant_client,
        test_collection_name: str,
        cleanup_qdrant_collection,
    ):
        """
        Test that writing larger vectors than expected raises an error.
        
        **Requirements: 3.4**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create collection with 64 dimensions
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=64, distance=Distance.COSINE),
        )
        
        # Try to insert vector with larger dimensions (128 instead of 64)
        wrong_dim_point = PointStruct(
            id=str(uuid.uuid4()),
            vector=[0.1] * 128,  # Too large
            payload={"content": "test"},
        )
        
        with pytest.raises(Exception):
            qdrant_client.upsert(
                collection_name=test_collection_name,
                points=[wrong_dim_point],
                wait=True,
            )


# =============================================================================
# Test Class: Batch Retry (Task 6.6)
# =============================================================================


class TestBatchRetry:
    """
    Test batch retry logic for storage operations.
    
    **Requirements: 3.5**
    
    WHEN batch write fails due to transient error THEN the OmniRAG System
    SHALL retry up to 3 times and succeed on recovery.
    """

    def test_vector_store_retry_logic(self):
        """
        Test that vector store retry logic works correctly.
        
        **Requirements: 3.5**
        """
        try:
            from core.storage.vector_store import QdrantVectorStore
        except ImportError:
            pytest.skip("qdrant-client not installed")
        
        from unittest.mock import patch, MagicMock
        
        # Create store with mocked client to avoid connection
        with patch('core.storage.vector_store.QdrantClient') as mock_client:
            with patch('core.storage.vector_store.load_storage_config', return_value={}):
                mock_client.return_value = MagicMock()
                store = QdrantVectorStore()
        
        # Track call count
        call_count = [0]
        
        def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Transient error")
            return "success"
        
        # Test retry with 2 attempts
        result = store._with_retry(
            op="test_op",
            collection="test_col",
            fn=flaky_operation,
            attempts=2,
            backoff_ms=10,  # Short backoff for test
        )
        
        assert result == "success"
        assert call_count[0] == 2, "Should have retried once"

    def test_vector_store_retry_exhausted(self):
        """
        Test that retry exhaustion raises the last error.
        
        **Requirements: 3.5**
        """
        try:
            from core.storage.vector_store import QdrantVectorStore
        except ImportError:
            pytest.skip("qdrant-client not installed")
        
        from unittest.mock import patch, MagicMock
        
        # Create store with mocked client to avoid connection
        with patch('core.storage.vector_store.QdrantClient') as mock_client:
            with patch('core.storage.vector_store.load_storage_config', return_value={}):
                mock_client.return_value = MagicMock()
                store = QdrantVectorStore()
        
        call_count = [0]
        
        def always_fail():
            call_count[0] += 1
            raise Exception(f"Persistent error {call_count[0]}")
        
        with pytest.raises(Exception) as exc_info:
            store._with_retry(
                op="test_op",
                collection="test_col",
                fn=always_fail,
                attempts=2,
                backoff_ms=10,
            )
        
        # Should have tried 3 times (1 initial + 2 retries)
        assert call_count[0] == 3
        assert "Persistent error" in str(exc_info.value)

    def test_keyword_store_retry_logic(self):
        """
        Test that keyword store retry logic works correctly.
        
        **Requirements: 3.5**
        """
        try:
            from core.storage.keyword_store import AsyncElasticsearchKeywordStore
        except ImportError:
            pytest.skip("elasticsearch not installed")
        
        from unittest.mock import patch, MagicMock
        
        # Create store with mocked clients to avoid connection
        with patch('core.storage.keyword_store.AsyncElasticsearch') as mock_async:
            with patch('core.storage.keyword_store.Elasticsearch') as mock_sync:
                with patch('core.storage.keyword_store.load_storage_config', return_value={}):
                    mock_async.return_value = MagicMock()
                    mock_sync.return_value = MagicMock()
                    store = AsyncElasticsearchKeywordStore()
        
        call_count = [0]
        
        def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Transient ES error")
            return "success"
        
        result = store._with_retry(
            op="test_op",
            index="test_index",
            fn=flaky_operation,
            attempts=2,
            backoff_ms=10,
        )
        
        assert result == "success"
        assert call_count[0] == 2

    @requires_qdrant
    def test_real_batch_upsert_success(
        self,
        qdrant_client,
        test_collection_name: str,
        cleanup_qdrant_collection,
    ):
        """
        Test real batch upsert succeeds.
        
        **Requirements: 3.5**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create collection
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=64, distance=Distance.COSINE),
        )
        
        # Batch upsert
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 64,
                payload={"content": f"doc_{i}"},
            )
            for i in range(10)
        ]
        
        # Should succeed
        qdrant_client.upsert(
            collection_name=test_collection_name,
            points=points,
            wait=True,
        )
        
        # Verify
        info = qdrant_client.get_collection(test_collection_name)
        assert info.points_count == 10


# =============================================================================
# Test Class: Dual-Write Consistency (Additional coverage for 3.3)
# =============================================================================


class TestDualWriteConsistency:
    """
    Test dual-write consistency between Qdrant and Elasticsearch.
    
    **Requirements: 3.3**
    
    WHEN vectors are written to Qdrant and keywords to Elasticsearch
    THEN the OmniRAG System SHALL maintain equal document counts in both stores.
    """

    @requires_qdrant
    @requires_elasticsearch
    @pytest.mark.asyncio
    async def test_dual_write_document_counts_match(
        self,
        qdrant_client,
        es_client,
        test_collection_name: str,
        test_index_name: str,
    ):
        """
        Test that document counts match between Qdrant and ES after dual write.
        
        **Requirements: 3.3**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        
        # Create Qdrant collection
        qdrant_client.create_collection(
            collection_name=test_collection_name,
            vectors_config=VectorParams(size=64, distance=Distance.COSINE),
        )
        
        # Create ES index
        es_client.indices.create(
            index=test_index_name,
            body={
                "mappings": {
                    "properties": {
                        "content": {"type": "text"},
                        "doc_id": {"type": "keyword"},
                    }
                }
            },
            ignore=400,  # Ignore if exists
        )
        
        # Write same documents to both
        num_docs = 15
        
        # Write to Qdrant
        qdrant_points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=[0.1] * 64,
                payload={
                    "content": f"Document content {i}",
                    "doc_id": f"doc_{i}",
                },
            )
            for i in range(num_docs)
        ]
        
        qdrant_client.upsert(
            collection_name=test_collection_name,
            points=qdrant_points,
            wait=True,
        )
        
        # Write to ES
        for i in range(num_docs):
            es_client.index(
                index=test_index_name,
                id=f"doc_{i}",
                document={
                    "content": f"Document content {i}",
                    "doc_id": f"doc_{i}",
                },
                refresh=True,
            )
        
        # Verify counts match
        qdrant_info = qdrant_client.get_collection(test_collection_name)
        qdrant_count = qdrant_info.points_count
        
        es_count = es_client.count(index=test_index_name)["count"]
        
        assert qdrant_count == num_docs, f"Qdrant should have {num_docs} points"
        assert es_count == num_docs, f"ES should have {num_docs} documents"
        assert qdrant_count == es_count, (
            f"Qdrant ({qdrant_count}) and ES ({es_count}) counts should match"
        )


# =============================================================================
# Test Class: Channel Isolation in Storage (Additional coverage for 3.6)
# =============================================================================


class TestChannelIsolationStorage:
    """
    Test channel isolation in storage layer.
    
    **Requirements: 3.6**
    
    WHEN querying channel_A's collection THEN the OmniRAG System
    SHALL return zero results for documents indexed under channel_B.
    """

    @requires_qdrant
    def test_channel_collections_are_isolated(
        self,
        qdrant_client,
    ):
        """
        Test that different channels have isolated collections.
        
        **Requirements: 3.6**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        from core.storage.channel_utils import channel_collection_name
        
        channel_a = f"channel_a_{uuid.uuid4().hex[:8]}"
        channel_b = f"channel_b_{uuid.uuid4().hex[:8]}"
        kb_name = f"test_kb_{uuid.uuid4().hex[:8]}"
        
        col_a = channel_collection_name(channel_a, kb_name, 1)
        col_b = channel_collection_name(channel_b, kb_name, 1)
        
        try:
            # Create collections for both channels
            for col in [col_a, col_b]:
                qdrant_client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(size=64, distance=Distance.COSINE),
                )
            
            # Insert data into channel_a only
            qdrant_client.upsert(
                collection_name=col_a,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=[0.5] * 64,
                        payload={"content": "Channel A data", "channel_id": channel_a},
                    )
                ],
                wait=True,
            )
            
            # Verify channel_a has data
            info_a = qdrant_client.get_collection(col_a)
            assert info_a.points_count == 1
            
            # Verify channel_b is empty
            info_b = qdrant_client.get_collection(col_b)
            assert info_b.points_count == 0, (
                "Channel B should have no data from Channel A"
            )
            
        finally:
            # Cleanup
            for col in [col_a, col_b]:
                try:
                    qdrant_client.delete_collection(col)
                except Exception:
                    pass

    @requires_qdrant
    def test_search_respects_channel_isolation(
        self,
        qdrant_client,
    ):
        """
        Test that search only returns results from the correct channel.
        
        **Requirements: 3.6**
        """
        from qdrant_client.models import Distance, PointStruct, VectorParams
        from core.storage.channel_utils import channel_collection_name
        
        channel_a = f"channel_a_{uuid.uuid4().hex[:8]}"
        channel_b = f"channel_b_{uuid.uuid4().hex[:8]}"
        kb_name = f"test_kb_{uuid.uuid4().hex[:8]}"
        
        col_a = channel_collection_name(channel_a, kb_name, 1)
        col_b = channel_collection_name(channel_b, kb_name, 1)
        
        try:
            # Create both collections
            for col in [col_a, col_b]:
                qdrant_client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(size=64, distance=Distance.COSINE),
                )
            
            # Insert different data into each channel
            qdrant_client.upsert(
                collection_name=col_a,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=[0.9] * 64,
                        payload={"content": "Channel A specific data"},
                    )
                ],
                wait=True,
            )
            
            qdrant_client.upsert(
                collection_name=col_b,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=[0.1] * 64,
                        payload={"content": "Channel B specific data"},
                    )
                ],
                wait=True,
            )
            
            # Search in channel_a using query_points (qdrant-client >= 1.7)
            results_a = qdrant_client.query_points(
                collection_name=col_a,
                query=[0.9] * 64,
                limit=10,
            )
            
            # Verify only channel_a data returned
            assert len(results_a.points) == 1
            assert "Channel A" in results_a.points[0].payload["content"]
            
            # Search in channel_b
            results_b = qdrant_client.query_points(
                collection_name=col_b,
                query=[0.1] * 64,
                limit=10,
            )
            
            # Verify only channel_b data returned
            assert len(results_b.points) == 1
            assert "Channel B" in results_b.points[0].payload["content"]
            
        finally:
            # Cleanup
            for col in [col_a, col_b]:
                try:
                    qdrant_client.delete_collection(col)
                except Exception:
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
