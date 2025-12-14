"""
RAPTOR Light - Lightweight wrapper for RAPTOR algorithm.

Design Philosophy:
- light vs deep is a BUSINESS decision, not a development limitation
- light version uses smaller cluster sizes and faster LLM settings
- Both versions use the same core algorithm from raptor_deep.py

For 100TB~500TB scale knowledge bases with:
- Videos, PDFs, ePub, Images, Office docs (complex flowcharts, manuals, tables)
- The system MUST provide full implementation capability

Usage:
- create_raptor_light_graph(): For quick summarization with fewer clusters
- create_raptor_deep_graph(): For comprehensive hierarchical summarization
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from core.algorithms.raptor_deep import (
    collect_texts,
    store_raptor,
    summarize_groups,
)


class RaptorLightState(TypedDict):
    """State for RAPTOR Light processing - uses same structure as Deep."""

    kb_name: str
    channel_id: str  # P0 Fix: Required for multi-tenant isolation
    prompt: str
    max_token: int
    threshold: float
    max_cluster: int  # Light uses smaller clusters (e.g., 4 vs 8)
    random_seed: int
    chunks: list[str]
    layers: list[list[int]]
    summaries: list[dict[str, Any]]
    meta: dict[str, Any]


def _apply_light_defaults(state: RaptorLightState) -> RaptorLightState:
    """Apply lighter defaults for faster processing."""
    # Light version uses fewer clusters for faster processing
    if not state.get("max_cluster"):
        state["max_cluster"] = 4  # vs 8 in deep
    if not state.get("prompt"):
        state["prompt"] = "简洁总结以下内容，不超过150字。"  # Shorter summary
    return state


async def light_collect(state: RaptorLightState) -> RaptorLightState:
    """Collect texts with light preprocessing.
    
    P0 Fix: Ensures channel_id is present for multi-tenant isolation
    before calling the deep collect_texts implementation.
    """
    # P0 Fix: Validate channel_id before processing
    if not state.get("channel_id"):
        raise ValueError("channel_id is required for RAPTOR Light processing to ensure tenant isolation")
    
    state = _apply_light_defaults(state)
    return await collect_texts(state)  # Reuse deep implementation


async def light_summarize(state: RaptorLightState) -> RaptorLightState:
    """Summarize with light settings."""
    return await summarize_groups(state)  # Reuse deep implementation


async def light_store(state: RaptorLightState) -> RaptorLightState:
    """Store results."""
    return await store_raptor(state)  # Reuse deep implementation


def create_raptor_light_graph():
    """
    Create RAPTOR Light graph.

    Differences from Deep:
    - Smaller max_cluster (4 vs 8) = faster clustering
    - Shorter summary prompts = fewer tokens
    - Same core algorithm quality

    Use this for:
    - Quick previews during ingestion
    - Real-time summarization requests
    - Lower-priority knowledge bases

    For production comprehensive indexing, use create_raptor_deep_graph().
    """
    graph = StateGraph(RaptorLightState)

    graph.add_node("collect", light_collect)
    graph.add_node("summarize", light_summarize)
    graph.add_node("store", light_store)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "summarize")
    graph.add_edge("summarize", "store")
    graph.add_edge("store", END)

    mem = MemorySaver()
    return graph.compile(checkpointer=mem)
