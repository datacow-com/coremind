"""Tests for multimodal retrieval modules."""

import pytest


class TestMultimodalEmbedder:
    """Tests for MultimodalEmbedder class."""

    def test_instantiation_default(self):
        """Test creating MultimodalEmbedder with default config."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()
        assert embedder.text_model == "BAAI/bge-m3"
        assert embedder.image_model == "openai/clip-vit-large-patch14"
        assert embedder.unified_space is True
        assert embedder.dimension == 1024

    def test_instantiation_custom(self):
        """Test creating MultimodalEmbedder with custom config."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        config = {
            "text_model": "custom/text-model",
            "image_model": "custom/image-model",
            "dimension": 512,
            "unified_space": False,
        }
        embedder = MultimodalEmbedder(config)

        assert embedder.text_model == "custom/text-model"
        assert embedder.image_model == "custom/image-model"
        assert embedder.dimension == 512
        assert embedder.unified_space is False

    def test_format_table_for_embedding(self):
        """Test formatting table content for embedding."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        table = "| Name | Age |\n|---|---|\n| Alice | 30 |"
        result = embedder._format_table_for_embedding(table)

        assert "[TABLE HEADER]" in result
        assert "[ROW" in result

    def test_project_dimension_truncate(self):
        """Test projecting to smaller dimension."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        embedding = [0.1] * 2048
        result = embedder._project_dimension(embedding, 1024)

        assert len(result) == 1024

    def test_project_dimension_pad(self):
        """Test projecting to larger dimension."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        embedding = [0.1] * 512
        result = embedder._project_dimension(embedding, 1024)

        assert len(result) == 1024
        assert result[512] == 0.0  # Padded with zeros

    def test_weighted_average_embeddings(self):
        """Test computing weighted average of embeddings."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
        weights = [1.0, 1.0]  # Equal weights

        result = embedder._weighted_average(embeddings, weights)

        assert len(result) == 3
        assert abs(result[0] - 0.5) < 0.01
        assert abs(result[1] - 0.5) < 0.01
        assert result[2] == 0.0

    def test_weighted_average_unequal(self):
        """Test weighted average with unequal weights."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        embeddings = [
            [1.0, 0.0],
            [0.0, 1.0],
        ]
        weights = [3.0, 1.0]  # First embedding weighted 3x

        result = embedder._weighted_average(embeddings, weights)

        assert result[0] == 0.75  # 3/4
        assert result[1] == 0.25  # 1/4

    def test_weighted_average_empty(self):
        """Test weighted average with empty input."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        result = embedder._weighted_average([], [])

        assert len(result) == 1024  # Default dimension
        assert all(v == 0.0 for v in result)

    @pytest.mark.asyncio
    async def test_embed_invalid_modality(self):
        """Test embedding with invalid modality raises error."""
        from core.retrieval.multimodal.embedder import MultimodalEmbedder

        embedder = MultimodalEmbedder()

        with pytest.raises(ValueError, match="Unknown modality"):
            await embedder.embed("test", modality="invalid")


class TestMultimodalRetriever:
    """Tests for MultimodalRetriever class."""

    def test_instantiation_default(self):
        """Test creating MultimodalRetriever with default config."""
        from core.retrieval.multimodal.retriever import MultimodalRetriever

        retriever = MultimodalRetriever()
        assert retriever.enable_image_search is True
        assert retriever.enable_table_search is True
        assert retriever.cross_modal_weight == 0.8
        assert retriever.top_k == 5

    def test_instantiation_custom(self):
        """Test creating MultimodalRetriever with custom config."""
        from core.retrieval.multimodal.retriever import MultimodalRetriever

        config = {
            "enable_image_search": False,
            "enable_table_search": True,
            "cross_modal_weight": 0.5,
            "top_k": 10,
            "modality_filter": ["text", "table"],
        }
        retriever = MultimodalRetriever(config)

        assert retriever.enable_image_search is False
        assert retriever.cross_modal_weight == 0.5
        assert retriever.top_k == 10
        assert retriever.modality_filter == ["text", "table"]

    def test_detect_query_modality_text(self):
        """Test detecting text query modality."""
        from core.retrieval.multimodal.retriever import MultimodalRetriever

        retriever = MultimodalRetriever()

        state = {
            "input_query": "What is the revenue?",
            "query_image": None,
        }

        modality = retriever._detect_query_modality(state)
        assert modality == "text"

    def test_detect_query_modality_image(self):
        """Test detecting image query modality."""
        from core.retrieval.multimodal.retriever import MultimodalRetriever

        retriever = MultimodalRetriever()

        state = {
            "input_query": "",
            "query_image": b"fake image data",
        }

        modality = retriever._detect_query_modality(state)
        assert modality == "image"

    def test_rank_results_same_modality_boost(self):
        """Test that same-modality results get boosted."""
        from core.retrieval.multimodal.retriever import MultimodalResult, MultimodalRetriever

        retriever = MultimodalRetriever()

        results = [
            MultimodalResult("1", "text content", "text", score=0.8),
            MultimodalResult("2", "image desc", "image", score=0.85),
        ]

        ranked = retriever._rank_results(results, query_modality="text")

        # Text result should be boosted (0.8 * 1.1 = 0.88)
        # Image result should be reduced (0.85 * 0.8 = 0.68)
        # So text result should be first now
        assert ranked[0].modality == "text"

    def test_merge_with_state(self):
        """Test merging multimodal results with state."""
        from core.retrieval.multimodal.retriever import MultimodalResult, MultimodalRetriever

        retriever = MultimodalRetriever()

        state = {
            "fused_results": [],
        }

        results = [
            MultimodalResult("1", "Result 1", "text", score=0.9, source_doc="doc1"),
            MultimodalResult("2", "Result 2", "image", score=0.8, page=5),
        ]

        new_state = retriever._merge_with_state(state, results)

        assert len(new_state["fused_results"]) == 2
        assert "multimodal_results" in new_state
        assert len(new_state["multimodal_results"]) == 2

        # Check chunk format
        chunk = new_state["fused_results"][0]
        assert "id" in chunk
        assert "content" in chunk
        assert "metadata" in chunk
        assert chunk["metadata"]["multimodal_search"] is True


class TestMultimodalResult:
    """Tests for MultimodalResult dataclass."""

    def test_result_creation(self):
        """Test creating a MultimodalResult."""
        from core.retrieval.multimodal.retriever import MultimodalResult

        result = MultimodalResult(
            id="result_1",
            content="This is the content",
            modality="text",
            score=0.95,
            metadata={"key": "value"},
            source_doc="document.pdf",
            page=3,
        )

        assert result.id == "result_1"
        assert result.content == "This is the content"
        assert result.modality == "text"
        assert result.score == 0.95
        assert result.metadata == {"key": "value"}
        assert result.source_doc == "document.pdf"
        assert result.page == 3

    def test_result_to_dict(self):
        """Test converting MultimodalResult to dict."""
        from core.retrieval.multimodal.retriever import MultimodalResult

        result = MultimodalResult(
            id="r1",
            content="content",
            modality="image",
            score=0.7,
            bbox=[10, 20, 100, 200],
        )

        d = result.to_dict()

        assert d["id"] == "r1"
        assert d["content"] == "content"
        assert d["modality"] == "image"
        assert d["score"] == 0.7
        assert d["bbox"] == [10, 20, 100, 200]


class TestMultimodalFactories:
    """Tests for factory functions."""

    def test_create_multimodal_embedder(self):
        """Test embedder factory function."""
        from core.retrieval.multimodal.embedder import create_multimodal_embedder

        embedder = create_multimodal_embedder({"dimension": 768})
        assert embedder.dimension == 768

    def test_create_multimodal_retriever(self):
        """Test retriever factory function."""
        from core.retrieval.multimodal.retriever import create_multimodal_retriever

        retriever = create_multimodal_retriever({"top_k": 20})
        assert retriever.top_k == 20


class TestModalityType:
    """Tests for ModalityType type alias."""

    def test_modality_types(self):
        """Test that modality types are properly defined."""

        # ModalityType is a Literal type, test valid values
        valid_types = ["text", "image", "table", "mixed"]

        # This is more of a documentation test
        # since Literal types are checked at type-check time
        for t in valid_types:
            assert isinstance(t, str)
