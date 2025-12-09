"""
MindMap Light - Knowledge structure visualization.

Design Philosophy:
- light vs deep is a BUSINESS decision, not a development limitation
- This module builds topic hierarchies from document content

For 100TB~500TB scale knowledge bases with:
- Videos, PDFs, ePub, Images, Office docs (complex flowcharts, manuals, tables)
- The system MUST provide full implementation capability

Usage:
- create_mindmap_light_graph(): For quick topic extraction
- Future: create_mindmap_deep_graph() for comprehensive structure analysis
"""

import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from core.llm.gateway import LLMGateway
from core.storage.index_router import list_all_meta
from server.config import settings


class MindMapState(TypedDict):
    """State for MindMap processing."""

    kb_name: str
    chunks: list[str]
    topics: list[dict[str, Any]]
    mindmap: dict[str, Any]
    meta: dict[str, Any]


async def collect_texts(state: MindMapState) -> MindMapState:
    """Collect texts from storage."""
    ms = list_all_meta()
    state["chunks"] = [
        str(m.get("content") or "") for m in ms if str(m.get("content") or "").strip()
    ]
    return state


async def extract_topics(state: MindMapState) -> MindMapState:
    """Extract topics from chunks using LLM."""
    gw = LLMGateway(provider=(settings.llm_provider or "dashscope"))
    chunks = state.get("chunks", [])

    if not chunks:
        state["topics"] = []
        return state

    # Sample chunks for topic extraction (limit for efficiency)
    sample_size = min(20, len(chunks))
    sample = chunks[:sample_size]
    context = "\n\n---\n\n".join(sample)

    prompt = """分析以下文档内容，提取主要主题和子主题，返回JSON格式：
{
  "topics": [
    {"name": "主题名", "subtopics": ["子主题1", "子主题2"], "keywords": ["关键词"]}
  ]
}"""

    try:
        out = await gw.chat(prompt=prompt, context=context)
        data = json.loads(out) if out else {}
        state["topics"] = data.get("topics", [])
    except Exception:
        state["topics"] = []

    return state


async def build_mindmap(state: MindMapState) -> MindMapState:
    """Build mindmap structure from topics."""
    topics = state.get("topics", [])
    kb_name = state.get("kb_name", "Knowledge Base")

    # Build hierarchical structure
    children = []
    for topic in topics:
        topic_node = {
            "name": topic.get("name", "Unknown"),
            "children": [{"name": st} for st in topic.get("subtopics", [])],
            "keywords": topic.get("keywords", []),
        }
        children.append(topic_node)

    state["mindmap"] = {"name": kb_name, "children": children}
    return state


async def store_mindmap(state: MindMapState) -> MindMapState:
    """Store mindmap to file."""
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "mindmaps")
    os.makedirs(out_dir, exist_ok=True)

    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.mindmap.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.get("mindmap", {}), f, ensure_ascii=False, indent=2)

    meta = state.get("meta") or {}
    meta["mindmap_path"] = path
    meta["topic_count"] = len(state.get("topics", []))
    state["meta"] = meta

    return state


def create_mindmap_light_graph():
    """
    Create MindMap extraction graph.

    Builds a topic hierarchy from document content for visualization.

    Use this for:
    - Knowledge base overview
    - Topic navigation UI
    - Document clustering visualization
    """
    graph = StateGraph(MindMapState)

    graph.add_node("collect", collect_texts)
    graph.add_node("topics", extract_topics)
    graph.add_node("mindmap", build_mindmap)
    graph.add_node("store", store_mindmap)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "topics")
    graph.add_edge("topics", "mindmap")
    graph.add_edge("mindmap", "store")
    graph.add_edge("store", END)

    mem = MemorySaver()
    return graph.compile(checkpointer=mem)
