"""
Shared fixtures and hypothesis strategies for state tests.

Requirements: 5.4 - Serialization round-trip compatibility
"""

from typing import Any

import pytest
from hypothesis import strategies as st

from core.state import ChunkingStrategy, StrategyConfig


# --- Hypothesis Strategies (P0/P1 Fix: ensure overlap < chunk_size) ---

# Valid chunking modes
CHUNKING_MODES = ["fixed", "semantic", "layout_aware", "table_first"]


# P0/P1 Fix: Generate valid ChunkingStrategy with overlap < chunk_size
@st.composite
def valid_chunking_strategy(draw):
    """Generate ChunkingStrategy with valid overlap < chunk_size constraint."""
    mode = draw(st.sampled_from(CHUNKING_MODES))
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    # Ensure overlap < chunk_size
    chunk_overlap = draw(st.integers(min_value=0, max_value=chunk_size - 1))
    preserve_tables = draw(st.booleans())
    return ChunkingStrategy(
        mode=mode,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        preserve_tables=preserve_tables,
    )


# Alias for backward compatibility
chunking_strategy = valid_chunking_strategy()


# P0/P1 Fix: Generate valid flat config with overlap < chunk_size
@st.composite
def valid_flat_config(draw):
    """Generate flat config dict with valid overlap < chunk_size constraint."""
    chunking_mode = draw(st.sampled_from(CHUNKING_MODES))
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    # Ensure overlap < chunk_size
    chunk_overlap = draw(st.integers(min_value=0, max_value=chunk_size - 1))
    preserve_tables = draw(st.booleans())
    return {
        "chunking_mode": chunking_mode,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "preserve_tables": preserve_tables,
    }


# Alias for backward compatibility
flat_config = valid_flat_config()


# P0/P1 Fix: Generate valid flat config with optional None values
@st.composite
def valid_flat_config_optional(draw):
    """Generate flat config dict with optional None values and valid constraints."""
    chunking_mode = draw(st.one_of(st.none(), st.sampled_from(CHUNKING_MODES)))
    chunk_size = draw(st.one_of(st.none(), st.integers(min_value=64, max_value=4096)))
    
    # If chunk_size is set, ensure overlap < chunk_size
    if chunk_size is not None:
        chunk_overlap = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=chunk_size - 1)))
    else:
        chunk_overlap = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=512)))
    
    preserve_tables = draw(st.one_of(st.none(), st.booleans()))
    return {
        "chunking_mode": chunking_mode,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "preserve_tables": preserve_tables,
    }


# Alias for backward compatibility
flat_config_optional = valid_flat_config_optional()

# channel_id generator - alphanumeric strings
channel_id = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=64,
)

# Empty or whitespace channel_id for edge case testing
invalid_channel_id = st.one_of(
    st.just(""),
    st.text(alphabet=" \t\n", min_size=1, max_size=10),
)


# --- Pytest Fixtures ---

@pytest.fixture
def default_strategy_config() -> StrategyConfig:
    """Default StrategyConfig with no overrides."""
    return StrategyConfig()


@pytest.fixture
def nested_only_config() -> StrategyConfig:
    """StrategyConfig with only nested chunking set."""
    return StrategyConfig(
        chunking=ChunkingStrategy(
            mode="semantic",
            chunk_size=1024,
            chunk_overlap=100,
            preserve_tables=False,
        )
    )


@pytest.fixture
def flat_only_config() -> StrategyConfig:
    """StrategyConfig with only flat fields set."""
    return StrategyConfig(
        chunking_mode="layout_aware",
        chunk_size=256,
        chunk_overlap=25,
        preserve_tables=True,
    )


@pytest.fixture
def mixed_config() -> StrategyConfig:
    """StrategyConfig with both flat and nested fields set."""
    return StrategyConfig(
        chunking=ChunkingStrategy(
            mode="fixed",
            chunk_size=512,
            chunk_overlap=50,
            preserve_tables=True,
        ),
        chunking_mode="semantic",
        chunk_size=1024,
        chunk_overlap=100,
        preserve_tables=False,
    )


@pytest.fixture
def sample_ingest_state_dict() -> dict[str, Any]:
    """Sample IngestState dict for testing."""
    return {
        "channel_id": "test_channel",
        "task_id": "task_001",
        "file_path": "test/doc.pdf",
        "file_type": "pdf",
        "batch_id": "batch_001",
        "kb_name": "test_kb",
        "version": 1,
        "strategy_config": {},
        "capability_loader": None,
        "raw_content": None,
        "extracted_text": None,
        "parsed_blocks": [],
        "images": [],
        "chunks": [],
        "vectors": [],
        "processing_stage": "upload",
        "retry_count": 0,
        "error_log": [],
        "progress": {},
        "quality_metrics": {},
    }


@pytest.fixture
def sample_retrieval_state_dict() -> dict[str, Any]:
    """Sample RetrievalState dict for testing."""
    return {
        "channel_id": "test_channel",
        "session_id": "session_001",
        "query_id": "query_001",
        "input_query": "Test query",
        "chat_history": [],
        "kb_names": ["test_kb"],
        "user_id": "user_001",
        "strategy_config": {},
        "capability_loader": None,
        "preprocessed_queries": [],
        "intent": {},
        "vector_results": [],
        "keyword_results": [],
        "fused_results": [],
        "reranked_results": [],
        "retrieved_chunks": [],
        "relevance_score": 0.0,
        "is_relevant": False,
        "loop_count": 0,
        "answer": "",
        "final_answer": "",
        "citations": [],
        "confidence": 0.0,
        "sources": [],
    }
