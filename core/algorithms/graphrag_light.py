"""
GraphRAG Light - Lightweight wrapper for GraphRAG algorithm.

Design Philosophy:
- light vs deep is a BUSINESS decision, not a development limitation
- light version uses faster extraction with lower concurrency
- Both versions use the same core algorithm from graphrag_deep.py

For 100TB~500TB scale knowledge bases with:
- Videos, PDFs, ePub, Images, Office docs (complex flowcharts, manuals, tables)
- The system MUST provide full implementation capability

Usage:
- create_graphrag_light_graph(): For quick entity extraction
- create_graphrag_deep_graph(): For comprehensive knowledge graph construction
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from core.algorithms.graphrag_deep import (
    collect_texts,
    extract_graph,
    store_graph,
)


class GraphLightState(TypedDict):
    """State for GraphRAG Light processing - uses same structure as Deep."""

    kb_name: str
    channel_id: str  # P0 Fix: Required for multi-tenant isolation
    language: str | None
    entity_types: list[str] | None
    chunks: list[str]
    graph: dict[str, Any]
    meta: dict[str, Any]


def _apply_light_defaults(state: GraphLightState) -> GraphLightState:
    """Apply lighter defaults for faster processing."""
    # Light version could limit entity types for faster extraction
    if not state.get("entity_types"):
        state["entity_types"] = ["人物", "组织", "地点"]  # Core entities only
    return state


async def light_collect(state: GraphLightState) -> GraphLightState:
    """Collect texts with light preprocessing.
    
    P0 Fix: Ensures channel_id is present for multi-tenant isolation
    before calling the deep collect_texts implementation.
    """
    # P0 Fix: Validate channel_id before processing
    if not state.get("channel_id"):
        raise ValueError("channel_id is required for GraphRAG Light processing to ensure tenant isolation")
    
    state = _apply_light_defaults(state)
    return await collect_texts(state)  # Reuse deep implementation


async def light_extract(state: GraphLightState) -> GraphLightState:
    """Extract graph with light settings."""
    return await extract_graph(state)  # Reuse deep implementation


async def light_store(state: GraphLightState) -> GraphLightState:
    """Store results."""
    return await store_graph(state)  # Reuse deep implementation


def create_graphrag_light_graph():
    """
    Create GraphRAG Light graph.

    Differences from Deep:
    - Limited entity types (core entities only)
    - Same extraction algorithm quality

    Use this for:
    - Quick entity extraction during ingestion
    - Real-time graph queries
    - Smaller document sets

    For production comprehensive graph building, use create_graphrag_deep_graph().
    """
    graph = StateGraph(GraphLightState)

    graph.add_node("collect", light_collect)
    graph.add_node("extract", light_extract)
    graph.add_node("store", light_store)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "extract")
    graph.add_edge("extract", "store")
    graph.add_edge("store", END)

    mem = MemorySaver()
    return graph.compile(checkpointer=mem)
