import pytest

from core.ingestion.nodes.chunker import SmartChunker
from core.state import IngestState


@pytest.fixture
def ingest_state():
    return IngestState(
        channel_id="test_channel",
        task_id="test_task",
        file_path="test.pdf",
        file_type="pdf",
        batch_id="batch_1",
        kb_name="test_kb",
        version=1,
        strategy_config={},
        capability_loader=None,
        processing_stage="parse",
        retry_count=0,
        error_log=[],
        progress={},
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[
            {"type": "text", "content": "Hello World. " * 50, "page": 1},
            {
                "type": "table",
                "content": "| Header | Value |\n|---|---|\n| A | 1 |",
                "page": 2,
                "bbox": [0, 0, 100, 100],
            },
            {"type": "text", "content": "Footer text.", "page": 2},
        ],
        images=[],
        chunks=[],
        vectors=[],
        quality_metrics={},
    )


@pytest.mark.asyncio
async def test_smart_chunker_fixed(ingest_state):
    # Test Fixed Chunking
    ingest_state["strategy_config"] = {
        "chunking": {"mode": "fixed", "chunk_size": 100, "chunk_overlap": 0}
    }
    chunker = SmartChunker()

    new_state = await chunker(ingest_state)

    assert len(new_state["chunks"]) > 0
    assert new_state["chunks"][0]["metadata"]["block_type"] == "text"
    # Fixed chunking joins text, so original structure is lost but text is preserved
    assert "Hello World" in new_state["chunks"][0]["content"]


@pytest.mark.asyncio
async def test_smart_chunker_table_first(ingest_state):
    # Test Table First Chunking
    ingest_state["strategy_config"] = {
        "chunking": {"mode": "table_first", "chunk_size": 100, "chunk_overlap": 0}
    }
    chunker = SmartChunker()

    new_state = await chunker(ingest_state)

    chunks = new_state["chunks"]
    table_chunks = [c for c in chunks if c["metadata"]["block_type"] == "table"]
    text_chunks = [c for c in chunks if c["metadata"]["block_type"] == "text"]

    assert len(table_chunks) == 1
    assert "| Header | Value |" in table_chunks[0]["content"]
    assert len(text_chunks) > 0
