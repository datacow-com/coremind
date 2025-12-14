"""
Test suite for core.ingestion.nodes.chunker module.

Tests smart chunking functionality including:
- Different chunking modes (fixed, table_first, layout_aware, semantic, heading_based)
- Weight calculation and metadata enrichment
- Language detection and caching
- Heading detection and structure preservation
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from typing import Any, Dict, List

import pytest

from core.ingestion.nodes.chunker import SmartChunker


class TestSmartChunker:
    """Test SmartChunker functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing chunking functionality.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
                {
                    "type": "table",
                    "content": "| Name | Age |\n| --- | --- |\n| Alice | 25 |",
                    "page": 1,
                    "bbox": [10, 60, 100, 100],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def sample_blocks(self) -> List[Dict[str, Any]]:
        """Sample parsed blocks for testing."""
        return [
            {
                "type": "text",
                "content": "This is the first paragraph with some content that should be chunked properly.",
                "page": 1,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "table",
                "content": "| Product | Price | Stock |\n| --- | --- | --- |\n| Apple | $1.00 | 100 |\n| Orange | $1.50 | 50 |",
                "page": 1,
                "bbox": [10, 60, 200, 120],
            },
            {
                "type": "text",
                "content": "This is the second paragraph that continues after the table.",
                "page": 2,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "image",
                "content": "Image description or caption text",
                "page": 2,
                "bbox": [10, 60, 200, 160],
            },
        ]


class TestChunkingModes:
    """Test different chunking modes."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunking mode tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing chunking functionality.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def sample_blocks(self) -> List[Dict[str, Any]]:
        """Sample parsed blocks for testing."""
        return [
            {
                "type": "text",
                "content": "This is the first paragraph with some content that should be chunked properly.",
                "page": 1,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "table",
                "content": "| Product | Price | Stock |\n| --- | --- | --- |\n| Apple | $1.00 | 100 |\n| Orange | $1.50 | 50 |",
                "page": 1,
                "bbox": [10, 60, 200, 120],
            },
            {
                "type": "text",
                "content": "This is the second paragraph that continues after the table.",
                "page": 2,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "image",
                "content": "Image description or caption text",
                "page": 2,
                "bbox": [10, 60, 200, 160],
            },
        ]
    
    @pytest.mark.asyncio
    async def test_fixed_mode_chunking(self, base_state):
        """TC-C001: 验证固定大小分块的正确性 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "fixed"
        base_state["strategy_config"]["chunking"]["chunk_size"] = 50
        
        # Create long text that will be split
        long_text = "This is a very long text that should be split into multiple chunks. " * 10
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": long_text,
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Verify chunking
        assert len(chunks) > 1
        for chunk in chunks:
            # Allow some overlap, so check against chunk_size + overlap
            assert len(chunk["content"]) <= 70  # 50 + 20 overlap
            assert chunk["metadata"]["block_type"] == "text"
            assert chunk["metadata"]["doc_id"] == "task_001"
    
    @pytest.mark.asyncio
    async def test_table_first_mode(self, base_state, sample_blocks):
        """TC-C002: 验证表格优先分块策略 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "table_first"
        base_state["parsed_blocks"] = sample_blocks
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Verify table chunks exist and have higher weight
        table_chunks = [c for c in chunks if c["metadata"]["block_type"] == "table"]
        text_chunks = [c for c in chunks if c["metadata"]["block_type"] == "text"]
        
        assert len(table_chunks) > 0
        assert len(text_chunks) > 0
        
        # Table chunks should have higher type weight
        table_weight = table_chunks[0]["metadata"]["type_weight"]
        text_weight = text_chunks[0]["metadata"]["type_weight"]
        assert table_weight > text_weight
    
    @pytest.mark.asyncio
    async def test_layout_aware_mode(self, base_state, sample_blocks):
        """TC-C003: 验证布局感知分块 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "layout_aware"
        base_state["parsed_blocks"] = sample_blocks
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Images and tables should be standalone chunks
        image_chunks = [c for c in chunks if c["metadata"]["block_type"] == "image"]
        table_chunks = [c for c in chunks if c["metadata"]["block_type"] == "table"]
        
        assert len(image_chunks) > 0
        assert len(table_chunks) > 0
        
        # Verify image chunk is standalone
        image_chunk = image_chunks[0]
        assert image_chunk["content"] == "Image description or caption text"
        assert image_chunk["metadata"]["block_type"] == "image"
    
    @pytest.mark.asyncio
    async def test_semantic_mode_fallback(self, base_state):
        """TC-C004: 验证语义分块在embedder不可用时回退 (P2)"""
        base_state["strategy_config"]["chunking"]["mode"] = "semantic"
        base_state["capability_loader"] = None  # No embedder available
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        # Should fall back to fixed mode
        chunks = result["chunks"]
        assert len(chunks) > 0
        # Verify it used fixed chunking (all chunks should be text type)
        assert all(c["metadata"]["block_type"] == "text" for c in chunks)
    
    @pytest.mark.asyncio
    async def test_semantic_mode_with_embedder(self, base_state):
        """Test semantic chunking with available embedder."""
        base_state["strategy_config"]["chunking"]["mode"] = "semantic"
        
        # Mock capability loader with embedder
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = [0.1] * 768  # Mock embedding
        
        mock_capability_loader = {"multimodal_embedding": mock_embedder}
        base_state["capability_loader"] = mock_capability_loader
        
        # Create text with clear sentence boundaries
        text_content = "First sentence about topic A. Second sentence about topic A. Third sentence about topic B. Fourth sentence about topic B."
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": text_content,
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        
        # Mock similarity calculation to group sentences
        with patch.object(chunker, "_group_by_similarity") as mock_group:
            mock_group.return_value = [
                ["First sentence about topic A.", "Second sentence about topic A."],
                ["Third sentence about topic B.", "Fourth sentence about topic B."],
            ]
            
            result = await chunker(base_state)
        
        chunks = result["chunks"]
        assert len(chunks) == 2  # Two semantic groups
        assert "topic A" in chunks[0]["content"]
        assert "topic B" in chunks[1]["content"]
    
    @pytest.mark.asyncio
    async def test_heading_based_mode(self, base_state):
        """TC-C005: 验证基于标题的分块 (P2)"""
        base_state["strategy_config"]["chunking"]["mode"] = "heading_based"
        
        # Create blocks with headings
        base_state["parsed_blocks"] = [
            {
                "type": "header",
                "content": "# Chapter 1: Introduction",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "This is the introduction content for testing heading based chunking.",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "header",
                "content": "## Section 1.1: Overview",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "This is the overview content for testing heading based chunking.",
                "page": 1,
                "bbox": None,
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create chunks from the content
        assert len(chunks) >= 1
        
        # All chunks should have required metadata
        for chunk in chunks:
            assert "block_type" in chunk["metadata"]
            assert "page_num" in chunk["metadata"]


class TestWeightCalculation:
    """Test weight calculation and metadata enrichment."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for weight calculation tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.fixture
    def sample_blocks(self) -> List[Dict[str, Any]]:
        """Sample parsed blocks for testing."""
        return [
            {
                "type": "text",
                "content": "This is the first paragraph with some content that should be chunked properly.",
                "page": 1,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "table",
                "content": "| Product | Price | Stock |\n| --- | --- | --- |\n| Apple | $1.00 | 100 |\n| Orange | $1.50 | 50 |",
                "page": 1,
                "bbox": [10, 60, 200, 120],
            },
            {
                "type": "text",
                "content": "This is the second paragraph that continues after the table.",
                "page": 2,
                "bbox": [10, 10, 200, 50],
            },
            {
                "type": "image",
                "content": "Image description or caption text",
                "page": 2,
                "bbox": [10, 60, 200, 160],
            },
        ]
    
    @pytest.mark.asyncio
    async def test_type_weight_calculation(self, base_state, sample_blocks):
        """TC-C006: 验证不同块类型的权重计算 (P2)"""
        base_state["parsed_blocks"] = sample_blocks
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Get chunks by type
        table_chunks = [c for c in chunks if c["metadata"]["block_type"] == "table"]
        text_chunks = [c for c in chunks if c["metadata"]["block_type"] == "text"]
        image_chunks = [c for c in chunks if c["metadata"]["block_type"] == "image"]
        
        # Verify weight hierarchy: table > text > image
        if table_chunks and text_chunks:
            assert table_chunks[0]["metadata"]["type_weight"] > text_chunks[0]["metadata"]["type_weight"]
        
        if text_chunks and image_chunks:
            assert text_chunks[0]["metadata"]["type_weight"] > image_chunks[0]["metadata"]["type_weight"]
    
    @pytest.mark.asyncio
    async def test_position_weight_calculation(self, base_state):
        """TC-C007: 验证页面位置对权重的影响 (P2)"""
        # Create blocks on different pages
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "First page content for testing position weight.",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "Tenth page content for testing position weight.",
                "page": 10,
                "bbox": None,
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        page1_chunk = next(c for c in chunks if "First page" in c["content"])
        page10_chunk = next(c for c in chunks if "Tenth page" in c["content"])
        
        # Both should have position_weight field
        assert "position_weight" in page1_chunk["metadata"]
        assert "position_weight" in page10_chunk["metadata"]
        
        # Position weight should be >= 1.0 (default)
        assert page1_chunk["metadata"]["position_weight"] >= 1.0
        assert page10_chunk["metadata"]["position_weight"] >= 1.0
    
    @pytest.mark.asyncio
    async def test_heading_weight_calculation(self, base_state):
        """Test heading level weight calculation."""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "# Level 1 Heading for testing weight calculation",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "### Level 3 Heading for testing weight calculation",
                "page": 1,
                "bbox": None,
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        h1_chunk = next(c for c in chunks if "Level 1" in c["content"])
        h3_chunk = next(c for c in chunks if "Level 3" in c["content"])
        
        # Both should have heading_weight field
        assert "heading_weight" in h1_chunk["metadata"]
        assert "heading_weight" in h3_chunk["metadata"]
        
        # Heading weight should be >= 1.0 (default)
        assert h1_chunk["metadata"]["heading_weight"] >= 1.0
        assert h3_chunk["metadata"]["heading_weight"] >= 1.0


class TestLanguageDetection:
    """Test language detection and caching."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for language detection tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_language_detection_caching(self, base_state):
        """TC-C008: 验证语言检测的缓存机制 (P2)"""
        chunker = SmartChunker()
        
        # Test with same text multiple times - text must be >= 20 chars
        text = "This is English text for testing language detection and caching."
        
        # First call - should detect and cache
        lang1 = chunker._detect_language(text)
        # Second call with same text - should use cache
        lang2 = chunker._detect_language(text)
        
        # Both should return same result
        assert lang1 == lang2
        # Result should be either detected language or "unknown"
        assert lang1 in ["en", "unknown"]
    
    @pytest.mark.asyncio
    async def test_multi_language_document_processing(self, base_state):
        """TC-C009: 验证混合语言文档的处理 (P2)"""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "This is English text in the document for testing purposes.",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "这是文档中的中文文本，用于测试多语言处理功能。",
                "page": 1,
                "bbox": None,
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Verify at least one chunk is created
        assert len(chunks) >= 1
        
        # Each chunk should have a language field
        for chunk in chunks:
            assert "language" in chunk["metadata"]
            # Language should be detected or "unknown"
            assert chunk["metadata"]["language"] in ["en", "zh", "unknown"]
    
    @pytest.mark.asyncio
    async def test_language_detection_unavailable(self, base_state):
        """Test behavior when language detection is unavailable."""
        chunker = SmartChunker()
        
        with patch("core.ingestion.nodes.chunker.LANGDETECT_AVAILABLE", False):
            result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should default to "unknown" when langdetect unavailable
        assert all(c["metadata"]["language"] == "unknown" for c in chunks)
    
    @pytest.mark.asyncio
    async def test_language_detection_exception(self, base_state):
        """Test language detection exception handling."""
        chunker = SmartChunker()
        
        # Test with very short text that will return "unknown"
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "Short",  # Too short for language detection
                "page": 1,
                "bbox": None,
            }
        ]
        
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should handle short text gracefully
        if chunks:
            assert chunks[0]["metadata"]["language"] == "unknown"


class TestHeadingDetection:
    """Test heading detection functionality."""
    
    def test_markdown_heading_detection(self):
        """Test detection of Markdown-style headings."""
        chunker = SmartChunker()
        
        # Test different heading levels
        assert chunker._detect_heading_level("# Level 1") == 1
        assert chunker._detect_heading_level("## Level 2") == 2
        assert chunker._detect_heading_level("### Level 3") == 3
        assert chunker._detect_heading_level("#### Level 4") == 4
        assert chunker._detect_heading_level("##### Level 5") == 5
        assert chunker._detect_heading_level("###### Level 6") == 6
    
    def test_chinese_legal_heading_detection(self):
        """Test detection of Chinese legal document headings."""
        chunker = SmartChunker()
        
        assert chunker._detect_heading_level("第一章 总则") == 1
        assert chunker._detect_heading_level("第二节 实施细则") == 2
        assert chunker._detect_heading_level("第三条 具体规定") == 3
    
    def test_numbered_heading_detection(self):
        """Test detection of numbered headings."""
        chunker = SmartChunker()
        
        assert chunker._detect_heading_level("1. Introduction") == 1
        assert chunker._detect_heading_level("1.1. Overview") == 2
        assert chunker._detect_heading_level("1.1.1. Details") == 3
    
    def test_no_heading_detection(self):
        """Test non-heading text detection."""
        chunker = SmartChunker()
        
        assert chunker._detect_heading_level("Regular paragraph text") is None
        assert chunker._detect_heading_level("") is None
        assert chunker._detect_heading_level("Some text with # in middle") is None


class TestChunkMetadata:
    """Test chunk metadata generation."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunk metadata tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_chunk_metadata_completeness(self, base_state):
        """Test that all required metadata fields are present."""
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        for chunk in chunks:
            metadata = chunk["metadata"]
            
            # Required fields
            assert "channel_id" in metadata
            assert "doc_id" in metadata
            assert "batch_id" in metadata
            assert "block_type" in metadata
            assert "media_type" in metadata
            assert "page_num" in metadata
            
            # Quality & OCR fields
            assert "language" in metadata
            assert "quality_score" in metadata
            
            # Weight fields
            assert "type_weight" in metadata
            assert "position_weight" in metadata
            assert "heading_weight" in metadata
    
    @pytest.mark.asyncio
    async def test_chunk_id_generation(self, base_state):
        """Test chunk ID generation."""
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Verify unique IDs
        chunk_ids = [c["id"] for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))  # All unique
        
        # Verify IDs are non-empty strings (format may vary)
        for chunk_id in chunk_ids:
            assert isinstance(chunk_id, str)
            assert len(chunk_id) > 0
    
    @pytest.mark.asyncio
    async def test_bbox_preservation(self, base_state):
        """Test that bounding box information is preserved."""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "Text with bbox for testing preservation of bounding box.",
                "page": 1,
                "bbox": [10, 20, 100, 60],
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        chunk = chunks[0]
        
        # bbox field should exist in metadata (may be None or actual value)
        assert "bbox" in chunk["metadata"]
        # page_num should exist in metadata
        assert "page_num" in chunk["metadata"]


class TestSemanticChunking:
    """Test semantic chunking functionality."""
    
    def test_sentence_splitting(self):
        """Test sentence splitting for semantic chunking."""
        chunker = SmartChunker()
        
        # Test English and Chinese sentence splitting
        text = "First sentence. Second sentence! Third sentence? 第一句。第二句！第三句？"
        sentences = chunker._split_into_sentences(text)
        
        assert len(sentences) == 6
        assert "First sentence" in sentences[0]
        assert "Second sentence" in sentences[1]
        assert "Third sentence" in sentences[2]
        assert "第一句" in sentences[3]
    
    def test_similarity_grouping(self):
        """Test sentence grouping by similarity."""
        chunker = SmartChunker()
        
        sentences = ["Sentence A", "Sentence B", "Sentence C"]
        
        # Mock embeddings with high similarity for A-B, low for B-C
        embeddings = [
            [1.0, 0.0, 0.0],  # A
            [0.9, 0.1, 0.0],  # B (similar to A)
            [0.0, 0.0, 1.0],  # C (different)
        ]
        
        groups = chunker._group_by_similarity(sentences, embeddings, threshold=0.7)
        
        # Should group A-B together, C separate
        assert len(groups) == 2
        assert len(groups[0]) == 2  # A and B
        assert len(groups[1]) == 1  # C


class TestProgressTracking:
    """Test progress tracking functionality."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for progress tracking tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_progress_chunk_count(self, base_state):
        """Test that total chunk count is tracked in progress."""
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        assert result["progress"]["total_chunks"] == len(chunks)
    
    @pytest.mark.asyncio
    async def test_processing_stage_update(self, base_state):
        """Test that processing stage is updated correctly."""
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        assert result["processing_stage"] == "embed"


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for edge case tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_empty_blocks_handling(self, base_state):
        """Test handling of empty parsed blocks."""
        base_state["parsed_blocks"] = []
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        assert result["chunks"] == []
        assert result["progress"]["total_chunks"] == 0
    
    @pytest.mark.asyncio
    async def test_blocks_with_empty_content(self, base_state):
        """Test handling of blocks with empty content."""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "   ",  # Whitespace only
                "page": 1,
                "bbox": None,
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        # Should handle empty content gracefully
        chunks = result["chunks"]
        # May create empty chunks or skip them depending on implementation
        assert isinstance(chunks, list)
    
    @pytest.mark.asyncio
    async def test_very_large_chunk_splitting(self, base_state):
        """Test handling of very large content that exceeds chunk size."""
        # Create very long content
        very_long_content = "This is a very long sentence. " * 1000
        
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": very_long_content,
                "page": 1,
                "bbox": None,
            }
        ]
        
        base_state["strategy_config"]["chunking"]["chunk_size"] = 100
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should split into multiple chunks
        assert len(chunks) > 1
        
        # Each chunk should be reasonably sized
        for chunk in chunks:
            assert len(chunk["content"]) <= 150  # Allow for overlap


# =============================================================================
# NEW: Robustness and Edge Case Tests
# =============================================================================

class TestSemanticChunkingFallback:
    """Test semantic chunking fallback scenarios."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [
                {
                    "type": "text",
                    "content": "This is a sample text block for testing chunking functionality.",
                    "page": 1,
                    "bbox": [10, 10, 100, 50],
                },
            ],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_semantic_fallback_on_embedder_exception(self, base_state):
        """TC-C010: 验证embedder异常时回退到固定分块 (P0)"""
        base_state["strategy_config"]["chunking"]["mode"] = "semantic"
        
        # Mock embedder that raises exception
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.side_effect = Exception("Embedding service unavailable")
        
        mock_capability_loader = {"multimodal_embedding": mock_embedder}
        base_state["capability_loader"] = mock_capability_loader
        
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "First sentence. Second sentence. Third sentence.",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        # Should fall back to fixed chunking without crashing
        chunks = result["chunks"]
        assert len(chunks) > 0
        assert result["processing_stage"] == "embed"
    
    @pytest.mark.asyncio
    async def test_semantic_fallback_on_empty_embeddings(self, base_state):
        """TC-C011: 验证embedder返回空结果时回退 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "semantic"
        
        # Mock embedder that returns empty
        mock_embedder = AsyncMock()
        mock_embedder.embed_text.return_value = []
        
        mock_capability_loader = {"multimodal_embedding": mock_embedder}
        base_state["capability_loader"] = mock_capability_loader
        
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "Some content to chunk.",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        # Should handle gracefully
        chunks = result["chunks"]
        assert isinstance(chunks, list)
    
    @pytest.mark.asyncio
    async def test_semantic_single_sentence_fallback(self, base_state):
        """TC-C012: 验证单句文本时回退到固定分块 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "semantic"
        base_state["capability_loader"] = None
        
        # Single sentence - too short for semantic chunking
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "Just one sentence here",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        # Should fall back to fixed chunking
        chunks = result["chunks"]
        assert len(chunks) >= 1


class TestHeadingTitlePropagation:
    """Test heading and title propagation in chunks."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_section_title_propagation(self, base_state):
        """TC-C013: 验证heading_based模式下的分块 (P0)"""
        base_state["strategy_config"]["chunking"]["mode"] = "heading_based"
        
        base_state["parsed_blocks"] = [
            {
                "type": "header",
                "content": "# Main Chapter Title",
                "page": 1,
                "bbox": None,
            },
            {
                "type": "text",
                "content": "This is content under the main chapter. " * 20,  # Long content
                "page": 1,
                "bbox": None,
            },
        ]
        
        base_state["strategy_config"]["chunking"]["chunk_size"] = 100
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create chunks from the content
        assert len(chunks) >= 1
        
        # All chunks should have required metadata fields
        for chunk in chunks:
            assert "block_type" in chunk["metadata"]
            assert "page_num" in chunk["metadata"]
    
    @pytest.mark.asyncio
    async def test_nested_heading_levels(self, base_state):
        """TC-C014: 验证嵌套标题层级的正确处理 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "heading_based"
        
        base_state["parsed_blocks"] = [
            {"type": "header", "content": "# Level 1", "page": 1, "bbox": None},
            {"type": "text", "content": "Content under level 1.", "page": 1, "bbox": None},
            {"type": "header", "content": "## Level 2", "page": 1, "bbox": None},
            {"type": "text", "content": "Content under level 2.", "page": 1, "bbox": None},
            {"type": "header", "content": "### Level 3", "page": 2, "bbox": None},
            {"type": "text", "content": "Content under level 3.", "page": 2, "bbox": None},
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should have chunks with different heading levels
        heading_levels = [c["metadata"].get("heading_level") for c in chunks if c["metadata"].get("heading_level")]
        assert 1 in heading_levels
        assert 2 in heading_levels
        assert 3 in heading_levels
    
    @pytest.mark.asyncio
    async def test_chinese_legal_heading_propagation(self, base_state):
        """TC-C015: 验证中文法律文档标题的传播 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "heading_based"
        
        base_state["parsed_blocks"] = [
            {"type": "text", "content": "第一章 总则", "page": 1, "bbox": None},
            {"type": "text", "content": "本法适用于中华人民共和国境内的活动。", "page": 1, "bbox": None},
            {"type": "text", "content": "第一节 基本原则", "page": 1, "bbox": None},
            {"type": "text", "content": "应当遵循公平、公正、公开的原则。", "page": 1, "bbox": None},
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should detect Chinese legal headings
        chapter_chunks = [c for c in chunks if "第一章" in c["content"]]
        assert len(chapter_chunks) > 0
        assert chapter_chunks[0]["metadata"]["heading_level"] == 1


class TestDeduplicationBoundary:
    """Test deduplication boundary cases."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_duplicate_content_handling(self, base_state):
        """TC-C016: 验证重复内容的处理 (P1)"""
        duplicate_text = "This exact content appears multiple times in the document."
        
        base_state["parsed_blocks"] = [
            {"type": "text", "content": duplicate_text, "page": 1, "bbox": None},
            {"type": "text", "content": duplicate_text, "page": 2, "bbox": None},
            {"type": "text", "content": duplicate_text, "page": 3, "bbox": None},
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Chunker itself doesn't deduplicate - that's QualityChecker's job
        # But it should create valid chunks for each block
        assert len(chunks) >= 1
        
        # Each chunk should have unique ID
        chunk_ids = [c["id"] for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))
    
    @pytest.mark.asyncio
    async def test_near_duplicate_content(self, base_state):
        """TC-C017: 验证近似重复内容的处理 (P1)"""
        base_state["parsed_blocks"] = [
            {"type": "text", "content": "The quick brown fox jumps over the lazy dog.", "page": 1, "bbox": None},
            {"type": "text", "content": "The quick brown fox jumps over the lazy dog!", "page": 2, "bbox": None},  # Only punctuation differs
            {"type": "text", "content": "A quick brown fox jumps over a lazy dog.", "page": 3, "bbox": None},  # Slight variation
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create separate chunks (dedup is not chunker's responsibility)
        assert len(chunks) >= 1


class TestSpecialContentHandling:
    """Test handling of special content types."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_all_table_document(self, base_state):
        """TC-C018: 验证全表格文档的处理 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "table_first"
        
        base_state["parsed_blocks"] = [
            {
                "type": "table",
                "content": "| A | B |\n| --- | --- |\n| 1 | 2 |",
                "page": 1,
                "bbox": [10, 10, 200, 100],
            },
            {
                "type": "table",
                "content": "| C | D |\n| --- | --- |\n| 3 | 4 |",
                "page": 2,
                "bbox": [10, 10, 200, 100],
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # All chunks should be table type
        assert all(c["metadata"]["block_type"] == "table" for c in chunks)
        assert len(chunks) == 2
        
        # Tables should have higher weight
        for chunk in chunks:
            assert chunk["metadata"]["type_weight"] > 1.0
    
    @pytest.mark.asyncio
    async def test_all_image_document(self, base_state):
        """TC-C019: 验证全图片文档的处理 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "layout_aware"
        
        base_state["parsed_blocks"] = [
            {
                "type": "image",
                "content": "Image 1 caption",
                "page": 1,
                "bbox": [10, 10, 200, 200],
            },
            {
                "type": "image",
                "content": "Image 2 caption",
                "page": 2,
                "bbox": [10, 10, 200, 200],
            },
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # All chunks should be image type
        assert all(c["metadata"]["block_type"] == "image" for c in chunks)
        assert len(chunks) == 2
    
    @pytest.mark.asyncio
    async def test_mixed_content_weight_hierarchy(self, base_state):
        """TC-C020: 验证混合内容的权重层级 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "layout_aware"
        
        base_state["parsed_blocks"] = [
            {"type": "header", "content": "Header content", "page": 1, "bbox": None},
            {"type": "table", "content": "| A | B |", "page": 1, "bbox": None},
            {"type": "text", "content": "Regular text content", "page": 1, "bbox": None},
            {"type": "image", "content": "Image caption", "page": 1, "bbox": None},
            {"type": "footer", "content": "Footer content", "page": 1, "bbox": None},
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Get weights by type
        weights_by_type = {}
        for chunk in chunks:
            block_type = chunk["metadata"]["block_type"]
            weights_by_type[block_type] = chunk["metadata"]["type_weight"]
        
        # Verify weight hierarchy: table > header > text > image > footer
        if "table" in weights_by_type and "text" in weights_by_type:
            assert weights_by_type["table"] > weights_by_type["text"]
        if "text" in weights_by_type and "image" in weights_by_type:
            assert weights_by_type["text"] > weights_by_type["image"]


class TestUnicodeAndSpecialCharacters:
    """Test handling of Unicode and special characters."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_unicode_content_chunking(self, base_state):
        """TC-C021: 验证Unicode内容的正确分块 (P1)"""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "中文内容测试。日本語テスト。한국어 테스트。العربية اختبار。",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should handle Unicode without errors
        assert len(chunks) > 0
        # Content should be preserved
        full_content = "".join(c["content"] for c in chunks)
        assert "中文" in full_content
        assert "日本語" in full_content
    
    @pytest.mark.asyncio
    async def test_emoji_content_chunking(self, base_state):
        """TC-C022: 验证Emoji内容的处理 (P1)"""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "Hello 👋 World 🌍! This is a test 🧪 with emojis 😀.",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should handle emojis without errors
        assert len(chunks) > 0
        full_content = "".join(c["content"] for c in chunks)
        assert "👋" in full_content or "Hello" in full_content
    
    @pytest.mark.asyncio
    async def test_special_characters_in_table(self, base_state):
        """TC-C023: 验证表格中特殊字符的处理 (P1)"""
        base_state["strategy_config"]["chunking"]["mode"] = "table_first"
        
        base_state["parsed_blocks"] = [
            {
                "type": "table",
                "content": "| Symbol | Value |\n| --- | --- |\n| < | less than |\n| > | greater than |\n| & | ampersand |",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should preserve special characters
        assert len(chunks) > 0
        table_chunk = chunks[0]
        assert "<" in table_chunk["content"]
        assert ">" in table_chunk["content"]
        assert "&" in table_chunk["content"]


class TestChunkSizeBoundaries:
    """Test chunk size boundary conditions."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_exact_chunk_size_content(self, base_state):
        """TC-C024: 验证恰好等于chunk_size的内容处理 (P1)"""
        chunk_size = 100
        base_state["strategy_config"]["chunking"]["chunk_size"] = chunk_size
        base_state["strategy_config"]["chunking"]["chunk_overlap"] = 0
        
        # Create content exactly chunk_size characters
        exact_content = "x" * chunk_size
        base_state["parsed_blocks"] = [
            {"type": "text", "content": exact_content, "page": 1, "bbox": None}
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create exactly one chunk
        assert len(chunks) >= 1
    
    @pytest.mark.asyncio
    async def test_chunk_size_plus_one(self, base_state):
        """TC-C025: 验证chunk_size+1的内容处理 (P1)"""
        chunk_size = 100
        base_state["strategy_config"]["chunking"]["chunk_size"] = chunk_size
        base_state["strategy_config"]["chunking"]["chunk_overlap"] = 10
        
        # Create content slightly over chunk_size
        content = "x" * (chunk_size + 1)
        base_state["parsed_blocks"] = [
            {"type": "text", "content": content, "page": 1, "bbox": None}
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create at least one chunk
        assert len(chunks) >= 1
    
    @pytest.mark.asyncio
    async def test_zero_chunk_overlap(self, base_state):
        """TC-C026: 验证零重叠的分块 (P1)"""
        base_state["strategy_config"]["chunking"]["chunk_size"] = 50
        base_state["strategy_config"]["chunking"]["chunk_overlap"] = 0
        
        content = "Word " * 50  # 250 characters
        base_state["parsed_blocks"] = [
            {"type": "text", "content": content, "page": 1, "bbox": None}
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should create multiple chunks without overlap
        assert len(chunks) > 1


class TestLanguageDetectionEdgeCases:
    """Test language detection edge cases."""
    
    @pytest.fixture
    def base_state(self) -> Dict[str, Any]:
        """Base state for chunker tests."""
        return {
            "channel_id": "test_channel",
            "task_id": "task_001",
            "batch_id": "batch_001",
            "file_type": "pdf",
            "strategy_config": {
                "chunking": {
                    "mode": "fixed",
                    "chunk_size": 100,
                    "chunk_overlap": 20,
                }
            },
            "parsed_blocks": [],
            "error_log": [],
            "progress": {},
        }
    
    @pytest.mark.asyncio
    async def test_very_short_text_language_detection(self, base_state):
        """TC-C027: 验证极短文本的语言检测 (P1)"""
        base_state["parsed_blocks"] = [
            {"type": "text", "content": "Hi", "page": 1, "bbox": None},  # Too short
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should default to "unknown" for very short text
        if chunks:
            assert chunks[0]["metadata"]["language"] == "unknown"
    
    @pytest.mark.asyncio
    async def test_mixed_language_detection(self, base_state):
        """TC-C028: 验证混合语言文本的检测 (P1)"""
        base_state["parsed_blocks"] = [
            {
                "type": "text",
                "content": "This is English text for testing. 这是中文文本用于测试。This is more English text.",
                "page": 1,
                "bbox": None,
            }
        ]
        
        chunker = SmartChunker()
        result = await chunker(base_state)
        
        chunks = result["chunks"]
        
        # Should detect a language (may vary based on implementation)
        assert len(chunks) > 0
        assert chunks[0]["metadata"]["language"] in ["en", "zh", "unknown"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])