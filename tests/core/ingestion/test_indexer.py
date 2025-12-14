"""
Test suite for core.ingestion.nodes.indexer module.

Tests dual indexing functionality including:
- Multi-tenant collection naming
- Vector and keyword indexing
- Multimodal content indexing (images, tables)
- Dimension validation and error handling
- Batch processing and retry mechanisms
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict, List

import pytest

from core.ingestion.nodes.indexer import DualIndexer


class TestDualIndexer:
    """Test DualIndexer functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {
                    "id": f"chunk_{i}",
                    "content": f"Content for chunk {i}",
                    "doc_id": "task_001",
                    "chunk_index": i,
                    "metadata": {
                        "block_type": "text",
                        "page_num": 1,
                        "bbox": [10, 10, 100, 50],
                    },
                }
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [
                {
                    "data": b"fake_image_data",
                    "page": 1,
                    "bbox": [10, 60, 100, 160],
                    "caption": "Test image",
                }
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client


class TestCollectionNaming:
    """Test collection naming for multi-tenant isolation."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_channel_collection_naming(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I001: 验证多租户collection命名隔离 (P0)"""
        base_state["channel_id"] = "tenant_123"
        base_state["kb_name"] = "documents"
        base_state["version"] = 2
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify vector collection naming
        expected_collection = "ch_tenant_123_kb_documents_v2"
        mock_vector_client.ensure_collection.assert_called()
        
        # Check the collection name used in ensure_collection call
        call_args = mock_vector_client.ensure_collection.call_args[0]
        assert call_args[0] == expected_collection
    
    @pytest.mark.asyncio
    async def test_no_channel_collection_naming(self, base_state, mock_vector_client, mock_keyword_client):
        """Test collection naming without channel_id."""
        base_state["channel_id"] = None
        base_state["kb_name"] = "documents"
        base_state["version"] = 1
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify collection naming without channel prefix
        expected_collection = "kb_documents_v1"
        call_args = mock_vector_client.ensure_collection.call_args[0]
        assert call_args[0] == expected_collection
    
    @pytest.mark.asyncio
    async def test_version_in_collection_name(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I002: 验证知识库版本在collection名中体现 (P1)"""
        base_state["version"] = 42
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify version is included
        call_args = mock_vector_client.ensure_collection.call_args[0]
        collection_name = call_args[0]
        assert "_v42_" in collection_name or collection_name.endswith("_v42")


class TestVectorIndexing:
    """Test vector indexing functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_vector_dimension_validation(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I003: 验证向量维度与配置一致性 (P1)"""
        base_state["strategy_config"]["embedding_dimensions"] = 512
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify collection created with correct dimensions
        call_args = mock_vector_client.ensure_collection.call_args
        assert call_args[1]["dim"] == 512
    
    @pytest.mark.asyncio
    async def test_batch_upsert_failure_retry(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I004: 验证批量插入失败的重试机制 (P1)"""
        # Mock upsert to fail
        mock_vector_client.upsert.side_effect = Exception("Vector upsert failed")
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should record error in error_log
        vector_errors = [e for e in result["error_log"] if e.get("backend") == "vector"]
        assert len(vector_errors) > 0
        assert "Vector upsert failed" in vector_errors[0]["error"]
    
    @pytest.mark.asyncio
    async def test_vector_indexing_disabled(self, base_state, mock_vector_client, mock_keyword_client):
        """Test behavior when vector backend is disabled."""
        base_state["strategy_config"]["vector_backend"] = "disabled"
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Vector client should not be called
        mock_vector_client.ensure_collection.assert_not_called()
        mock_vector_client.upsert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_quantization_configuration(self, base_state, mock_vector_client, mock_keyword_client):
        """Test quantization configuration."""
        base_state["strategy_config"]["enable_quantization"] = False
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify quantization setting
        call_args = mock_vector_client.ensure_collection.call_args
        assert call_args[1]["enable_quantization"] is False


class TestKeywordIndexing:
    """Test keyword indexing functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_elasticsearch_indexing(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I008: 验证ES索引的正确创建和数据插入 (P1)"""
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify ES index creation and data insertion
        mock_keyword_client.ensure_index.assert_called_once()
        mock_keyword_client.bulk_upsert.assert_called_once()
        
        # Verify index name
        index_name = mock_keyword_client.ensure_index.call_args[0][0]
        assert "test_channel" in index_name
        assert "test_kb" in index_name
    
    @pytest.mark.asyncio
    async def test_keyword_indexing_disabled(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I009: 验证禁用关键词索引时跳过ES (P1)"""
        base_state["strategy_config"]["keyword_backend"] = "disabled"
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Keyword client should not be called
        mock_keyword_client.ensure_index.assert_not_called()
        mock_keyword_client.bulk_upsert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_keyword_batch_processing(self, base_state, mock_vector_client, mock_keyword_client):
        """Test keyword indexing batch processing."""
        # Create many chunks to test batching
        base_state["chunks"] = [
            {
                "id": f"chunk_{i}",
                "content": f"Content {i}",
                "doc_id": "task_001",
                "chunk_index": i,
                "metadata": {"block_type": "text"},
            }
            for i in range(250)  # More than batch size
        ]
        base_state["vectors"] = [[0.1] * 768 for _ in range(250)]
        base_state["strategy_config"]["index_batch_size"] = 100
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Should call bulk_upsert multiple times for batching
        assert mock_keyword_client.bulk_upsert.call_count >= 2


class TestMultimodalIndexing:
    """Test multimodal content indexing."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [{"data": b"fake_image_data", "page": 1, "bbox": [10, 60, 100, 160], "caption": "Test image"}],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_image_collection_creation(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I005: 验证图片专用collection的创建 (P2)"""
        # Mock multimodal embedder
        mock_embedder = AsyncMock()
        mock_embedder.embed_image.return_value = [0.2] * 768
        
        mock_capability_loader = Mock()
        mock_capability_loader.get.return_value = mock_embedder
        base_state["capability_loader"] = mock_capability_loader
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify image collection was created
        collection_calls = mock_vector_client.ensure_collection.call_args_list
        image_collection_created = any(
            "_images" in call[0][0] for call in collection_calls
        )
        assert image_collection_created
        
        # Verify image data was indexed
        upsert_calls = mock_vector_client.upsert.call_args_list
        image_upsert = any(
            "_images" in call[0][0] for call in upsert_calls
        )
        assert image_upsert
    
    @pytest.mark.asyncio
    async def test_table_collection_creation(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I006: 验证表格专用collection的创建 (P2)"""
        # Add table chunks
        base_state["chunks"].append({
            "id": "table_chunk_1",
            "content": "| Name | Age |\n| --- | --- |\n| Alice | 25 |",
            "doc_id": "task_001",
            "chunk_index": 5,
            "metadata": {
                "block_type": "table",
                "page_num": 1,
                "bbox": [10, 60, 200, 120],
            },
        })
        base_state["vectors"].append([0.3] * 768)
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Verify table collection was created
        collection_calls = mock_vector_client.ensure_collection.call_args_list
        table_collection_created = any(
            "_tables" in call[0][0] for call in collection_calls
        )
        assert table_collection_created
        
        # Verify table metadata
        upsert_calls = mock_vector_client.upsert.call_args_list
        table_upsert_call = next(
            call for call in upsert_calls if "_tables" in call[0][0]
        )
        table_points = table_upsert_call[0][1]
        assert len(table_points) > 0
        assert table_points[0].payload["block_type"] == "table"
    
    @pytest.mark.asyncio
    async def test_no_multimodal_embedder_behavior(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I007: 验证缺少多模态embedder时跳过图片索引 (P1)"""
        base_state["capability_loader"] = None
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should log warning about missing embedder
        warnings = [e for e in result["error_log"] if "warning" in e]
        multimodal_warnings = [
            w for w in warnings 
            if "No multimodal embedder available" in w.get("warning", "")
        ]
        assert len(multimodal_warnings) > 0
    
    @pytest.mark.asyncio
    async def test_multimodal_indexing_disabled(self, base_state, mock_vector_client, mock_keyword_client):
        """Test behavior when multimodal indexing is disabled."""
        base_state["strategy_config"]["enable_multimodal_index"] = False
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Should not create image/table collections
        collection_calls = mock_vector_client.ensure_collection.call_args_list
        multimodal_collections = [
            call for call in collection_calls 
            if "_images" in call[0][0] or "_tables" in call[0][0]
        ]
        assert len(multimodal_collections) == 0


class TestTableUtilities:
    """Test table utility functions."""
    
    def test_table_row_estimation(self):
        """Test table row count estimation."""
        indexer = DualIndexer()
        
        # Test markdown table
        table_content = """| Name | Age | City |
| --- | --- | --- |
| Alice | 25 | NYC |
| Bob | 30 | LA |
| Charlie | 35 | SF |"""
        
        row_count = indexer._estimate_table_rows(table_content)
        # 5 lines with | - 1 separator = 4 (header + 3 data rows)
        assert row_count == 4
    
    def test_table_column_estimation(self):
        """Test table column count estimation."""
        indexer = DualIndexer()
        
        # Test markdown table
        table_content = """| Name | Age | City | Country |
| --- | --- | --- | --- |
| Alice | 25 | NYC | USA |"""
        
        col_count = indexer._estimate_table_cols(table_content)
        assert col_count == 4  # 5 pipes - 1 = 4 columns
    
    def test_empty_table_handling(self):
        """Test handling of empty table content."""
        indexer = DualIndexer()
        
        assert indexer._estimate_table_rows("") == 0
        assert indexer._estimate_table_cols("") == 0
        assert indexer._estimate_table_rows(None) == 0
        assert indexer._estimate_table_cols(None) == 0


class TestProgressTracking:
    """Test progress tracking functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [{"data": b"fake_image_data", "page": 1, "bbox": [10, 60, 100, 160], "caption": "Test image"}],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_vector_indexing_progress(self, base_state, mock_vector_client, mock_keyword_client):
        """Test vector indexing progress tracking."""
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Verify progress tracking
        assert "progress" in result
        assert "indexed_vector" in result["progress"]
        assert result["progress"]["indexed_vector"] >= 0
    
    @pytest.mark.asyncio
    async def test_keyword_indexing_progress(self, base_state, mock_vector_client, mock_keyword_client):
        """Test keyword indexing progress tracking."""
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Verify progress tracking
        assert "indexed_keyword" in result["progress"]
        assert result["progress"]["indexed_keyword"] >= 0
    
    @pytest.mark.asyncio
    async def test_multimodal_indexing_progress(self, base_state, mock_vector_client, mock_keyword_client):
        """Test multimodal indexing progress tracking."""
        # Mock multimodal embedder
        mock_embedder = AsyncMock()
        mock_embedder.embed_image.return_value = [0.2] * 768
        
        mock_capability_loader = Mock()
        mock_capability_loader.get.return_value = mock_embedder
        base_state["capability_loader"] = mock_capability_loader
        
        # Add table chunks
        base_state["chunks"].append({
            "id": "table_chunk_1",
            "content": "Table content",
            "doc_id": "task_001",
            "chunk_index": 5,
            "metadata": {"block_type": "table"},
        })
        base_state["vectors"].append([0.3] * 768)
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Verify multimodal progress tracking
        assert "indexed_images" in result["progress"]
        assert "indexed_tables" in result["progress"]


class TestErrorHandling:
    """Test error handling and recovery."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [{"data": b"fake_image_data", "page": 1, "bbox": [10, 60, 100, 160], "caption": "Test image"}],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_vector_client_exception_propagates(self, base_state, mock_keyword_client):
        """Test that vector client exceptions propagate."""
        # Mock vector client to raise exception
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection.side_effect = Exception("Vector DB error")
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            # Exception should propagate
            with pytest.raises(Exception, match="Vector DB error"):
                await indexer(base_state)
    
    @pytest.mark.asyncio
    async def test_keyword_client_exception_propagates(self, base_state, mock_vector_client):
        """Test that keyword client exceptions propagate."""
        # Mock keyword client to raise exception
        mock_keyword_client = AsyncMock()
        mock_keyword_client.ensure_index.side_effect = Exception("ES error")
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            # Exception should propagate
            with pytest.raises(Exception, match="ES error"):
                await indexer(base_state)
    
    @pytest.mark.asyncio
    async def test_image_embedding_failure(self, base_state, mock_vector_client, mock_keyword_client):
        """Test handling of image embedding failures."""
        # Mock embedder that fails
        mock_embedder = AsyncMock()
        mock_embedder.embed_image.side_effect = Exception("Image embedding failed")
        
        mock_capability_loader = Mock()
        mock_capability_loader.get.return_value = mock_embedder
        base_state["capability_loader"] = mock_capability_loader
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should record image embedding errors
        image_errors = [e for e in result["error_log"] if e.get("backend") == "multimodal"]
        assert len(image_errors) > 0


class TestProcessingStageUpdate:
    """Test processing stage updates."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {"block_type": "text"}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_processing_stage_finalize(self, base_state, mock_vector_client, mock_keyword_client):
        """Test processing stage is updated to finalize."""
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        assert result["processing_stage"] == "finalize"


class TestBatchProcessing:
    """Test batch processing functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 500,
            },
            "chunks": [],
            "vectors": [],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self, base_state, mock_vector_client, mock_keyword_client):
        """Test processing of large batches."""
        # Create large number of chunks
        large_chunk_count = 1500
        base_state["chunks"] = [
            {
                "id": f"chunk_{i}",
                "content": f"Content {i}",
                "doc_id": "task_001",
                "chunk_index": i,
                "metadata": {"block_type": "text"},
            }
            for i in range(large_chunk_count)
        ]
        base_state["vectors"] = [[0.1] * 768 for _ in range(large_chunk_count)]
        base_state["strategy_config"]["index_batch_size"] = 500
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Should process in multiple batches
        assert mock_vector_client.upsert.call_count >= 3  # 1500 / 500 = 3 batches
        assert mock_keyword_client.bulk_upsert.call_count >= 3


# =============================================================================
# NEW: Robustness and Edge Case Tests
# =============================================================================

class TestRetryMechanisms:
    """Test retry mechanisms and partial failure handling."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {
                    "id": f"chunk_{i}",
                    "content": f"Content for chunk {i}",
                    "doc_id": "task_001",
                    "chunk_index": i,
                    "metadata": {"block_type": "text", "page_num": 1},
                }
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_partial_batch_failure_isolation(self, base_state, mock_keyword_client):
        """TC-I010: 验证单批次失败不影响其他批次 (P0)"""
        # Create multiple batches
        base_state["chunks"] = [
            {
                "id": f"chunk_{i}",
                "content": f"Content {i}",
                "doc_id": "task_001",
                "chunk_index": i,
                "metadata": {"block_type": "text"},
            }
            for i in range(300)  # 3 batches with batch_size=100
        ]
        base_state["vectors"] = [[0.1] * 768 for _ in range(300)]
        base_state["strategy_config"]["index_batch_size"] = 100
        
        # Mock vector client to fail on second batch only
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection = AsyncMock()
        call_count = [0]
        
        async def selective_failure(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:  # Fail on second batch
                raise Exception("Batch 2 failed")
            return None
        
        mock_vector_client.upsert = AsyncMock(side_effect=selective_failure)
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should have recorded error for batch 2
        vector_errors = [e for e in result["error_log"] if e.get("backend") == "vector"]
        assert len(vector_errors) == 1
        assert vector_errors[0]["batch_start"] == 100  # Second batch starts at index 100
        
        # Other batches should have succeeded (3 calls total, 1 failed)
        assert mock_vector_client.upsert.call_count == 3
    
    @pytest.mark.asyncio
    async def test_vector_and_keyword_independent_failure(self, base_state):
        """TC-I011: 验证向量和关键词索引失败相互独立 (P0)"""
        # Mock vector client to succeed
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection = AsyncMock()
        mock_vector_client.upsert = AsyncMock()
        
        # Mock keyword client to fail
        mock_keyword_client = AsyncMock()
        mock_keyword_client.ensure_index = AsyncMock()
        mock_keyword_client.bulk_upsert = AsyncMock(side_effect=Exception("ES unavailable"))
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Vector indexing should have succeeded
        mock_vector_client.upsert.assert_called()
        
        # Keyword error should be recorded
        keyword_errors = [e for e in result["error_log"] if e.get("backend") == "keyword"]
        assert len(keyword_errors) > 0
        
        # Processing should continue to finalize
        assert result["processing_stage"] == "finalize"
    
    @pytest.mark.asyncio
    async def test_ensure_collection_failure_propagates(self, base_state, mock_keyword_client):
        """TC-I012: 验证collection创建失败会传播异常 (P1)"""
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection = AsyncMock(
            side_effect=Exception("Collection creation failed")
        )
        mock_vector_client.upsert = AsyncMock()
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            # Collection creation failure should propagate
            with pytest.raises(Exception, match="Collection creation failed"):
                await indexer(base_state)


class TestCrossTenantIsolation:
    """Test cross-tenant isolation in indexing."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_channel_id_in_payload(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I013: 验证channel_id正确写入payload (P0)"""
        base_state["channel_id"] = "tenant_xyz"
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Check vector upsert payload
        upsert_call = mock_vector_client.upsert.call_args
        points = upsert_call[0][1]  # Second argument is points list
        
        for point in points:
            assert point.payload["channel_id"] == "tenant_xyz"
    
    @pytest.mark.asyncio
    async def test_different_channels_different_collections(self, mock_vector_client, mock_keyword_client):
        """TC-I014: 验证不同channel使用不同collection (P0)"""
        indexer = DualIndexer()
        
        collection_names = []
        
        async def capture_collection_name(name, **kwargs):
            collection_names.append(name)
        
        mock_vector_client.ensure_collection = AsyncMock(side_effect=capture_collection_name)
        
        # Index for channel A
        state_a = {
            "channel_id": "channel_a",
            "task_id": "task_001",
            "kb_name": "shared_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "disabled",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [{"id": "c1", "content": "A", "doc_id": "t1", "chunk_index": 0, "metadata": {}}],
            "vectors": [[0.1] * 768],
            "error_log": [],
            "progress": {},
        }
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(state_a)
        
        # Index for channel B
        state_b = state_a.copy()
        state_b["channel_id"] = "channel_b"
        state_b["chunks"] = [{"id": "c2", "content": "B", "doc_id": "t2", "chunk_index": 0, "metadata": {}}]
        state_b["vectors"] = [[0.2] * 768]
        state_b["error_log"] = []
        state_b["progress"] = {}
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(state_b)
        
        # Should have created different collections
        assert len(collection_names) == 2
        assert "channel_a" in collection_names[0]
        assert "channel_b" in collection_names[1]
        assert collection_names[0] != collection_names[1]


class TestDimensionMismatch:
    """Test vector dimension mismatch handling."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_missing_embedding_dimensions_config(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I015: 验证缺少embedding_dimensions配置时使用默认值 (P1)"""
        del base_state["strategy_config"]["embedding_dimensions"]
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Should use default dimension (1024)
        call_args = mock_vector_client.ensure_collection.call_args
        assert call_args[1]["dim"] == 1024  # Default value
    
    @pytest.mark.asyncio
    async def test_vector_dimension_mismatch_error(self, base_state, mock_keyword_client):
        """TC-I016: 验证向量维度不匹配时的错误处理 (P1)"""
        # Set config dimension to 768 but provide 512-dim vectors
        base_state["strategy_config"]["embedding_dimensions"] = 768
        base_state["vectors"] = [[0.1] * 512 for _ in range(5)]  # Wrong dimension
        
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection = AsyncMock()
        mock_vector_client.upsert = AsyncMock(
            side_effect=Exception("Vector dimension mismatch: expected 768, got 512")
        )
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should record dimension mismatch error
        vector_errors = [e for e in result["error_log"] if e.get("backend") == "vector"]
        assert len(vector_errors) > 0
        assert "dimension" in vector_errors[0]["error"].lower()


class TestServiceUnavailability:
    """Test handling of service unavailability."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_qdrant_unavailable_propagates_error(self, base_state, mock_keyword_client):
        """TC-I017: 验证Qdrant不可用时异常传播 (P0)"""
        mock_vector_client = AsyncMock()
        mock_vector_client.ensure_collection = AsyncMock(
            side_effect=ConnectionError("Qdrant service unavailable")
        )
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            # Qdrant unavailable should propagate exception
            with pytest.raises(ConnectionError, match="Qdrant service unavailable"):
                await indexer(base_state)
    
    @pytest.mark.asyncio
    async def test_elasticsearch_unavailable_propagates_error(self, base_state, mock_vector_client):
        """TC-I018: 验证Elasticsearch不可用时异常传播 (P0)"""
        mock_keyword_client = AsyncMock()
        mock_keyword_client.ensure_index = AsyncMock(
            side_effect=ConnectionError("Elasticsearch service unavailable")
        )
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            # ES unavailable should propagate exception
            with pytest.raises(ConnectionError, match="Elasticsearch service unavailable"):
                await indexer(base_state)
    
    @pytest.mark.asyncio
    async def test_vector_backend_disabled_skips_qdrant(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I019: 验证禁用向量后端时跳过Qdrant (P1)"""
        base_state["strategy_config"]["vector_backend"] = "disabled"
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Vector client should not be called
        mock_vector_client.ensure_collection.assert_not_called()
        
        # Keyword indexing should still work
        mock_keyword_client.ensure_index.assert_called()
        
        # Should complete successfully
        assert result["processing_stage"] == "finalize"


class TestEmptyDataHandling:
    """Test handling of empty or missing data."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": True,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [
                {"id": f"chunk_{i}", "content": f"Content {i}", "doc_id": "task_001", "chunk_index": i, "metadata": {}}
                for i in range(5)
            ],
            "vectors": [[0.1] * 768 for _ in range(5)],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_empty_chunks_list(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I020: 验证空chunks列表的处理 (P1)"""
        base_state["chunks"] = []
        base_state["vectors"] = []
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should complete without errors
        assert result["processing_stage"] == "finalize"
        # Should not call upsert with empty data
        # (ensure_collection may still be called)
    
    @pytest.mark.asyncio
    async def test_empty_images_list(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I021: 验证空images列表的处理 (P1)"""
        base_state["images"] = []
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should complete without image indexing errors
        image_errors = [e for e in result["error_log"] if "image" in str(e.get("backend", "")).lower()]
        assert len(image_errors) == 0
    
    @pytest.mark.asyncio
    async def test_image_without_data(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I022: 验证图片缺少data字段的处理 (P1)"""
        base_state["images"] = [
            {"page": 1, "bbox": [10, 10, 100, 100], "caption": "No data"},  # Missing 'data'
        ]
        
        # Mock embedder
        mock_embedder = AsyncMock()
        mock_embedder.embed_image.return_value = [0.1] * 768
        mock_capability_loader = Mock()
        mock_capability_loader.get.return_value = mock_embedder
        base_state["capability_loader"] = mock_capability_loader
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            result = await indexer(base_state)
        
        # Should skip image without data, not crash
        assert result["processing_stage"] == "finalize"


class TestMetadataPreservation:
    """Test metadata preservation during indexing."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for indexer tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "kb_name": "test_kb",
            "version": 1,
            "strategy_config": {
                "vector_backend": "auto",
                "keyword_backend": "elasticsearch",
                "enable_multimodal_index": False,
                "embedding_dimensions": 768,
                "enable_quantization": True,
                "index_batch_size": 100,
            },
            "chunks": [],
            "vectors": [],
            "images": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def mock_vector_client(self):
        """Mock vector store client."""
        client = AsyncMock()
        client.ensure_collection = AsyncMock()
        client.upsert = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_keyword_client(self):
        """Mock keyword store client."""
        client = AsyncMock()
        client.ensure_index = AsyncMock()
        client.bulk_upsert = AsyncMock()
        return client
    
    @pytest.mark.asyncio
    async def test_chunk_metadata_in_payload(self, base_state, mock_vector_client, mock_keyword_client):
        """TC-I023: 验证chunk元数据正确写入payload (P1)"""
        base_state["chunks"] = [
            {
                "id": "chunk_001",
                "content": "Test content",
                "doc_id": "task_001",
                "chunk_index": 0,
                "metadata": {
                    "block_type": "text",
                    "page_num": 5,
                    "bbox": [10, 20, 100, 60],
                    "quality_score": 0.95,
                    "language": "en",
                    "custom_field": "preserved",
                },
            }
        ]
        base_state["vectors"] = [[0.1] * 768]
        
        indexer = DualIndexer()
        
        with patch("core.ingestion.nodes.indexer.get_vector_client", return_value=mock_vector_client), \
             patch("core.ingestion.nodes.indexer.get_keyword_client", return_value=mock_keyword_client):
            
            await indexer(base_state)
        
        # Check vector payload
        upsert_call = mock_vector_client.upsert.call_args
        points = upsert_call[0][1]
        payload = points[0].payload
        
        assert payload["content"] == "Test content"
        assert payload["doc_id"] == "task_001"
        assert payload["chunk_index"] == 0
        assert "metadata" in payload
        assert payload["metadata"]["custom_field"] == "preserved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])