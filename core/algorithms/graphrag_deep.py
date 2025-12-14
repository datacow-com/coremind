import asyncio
import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.llm.gateway import LLMGateway
from core.storage.index_router import list_kb_chunks, scroll_kb_chunks
from server.config import settings


class GraphDeepState(TypedDict):
    kb_name: str
    channel_id: str  # P0 Fix: Added for multi-tenant isolation
    language: str | None
    entity_types: list[str] | None
    chunks: list[str]
    graph: dict[str, Any]
    communities: list[dict[str, Any]]  # Louvain communities
    meta: dict[str, Any]


async def collect_texts(state: GraphDeepState) -> GraphDeepState:
    """
    P0 Fix: Collect texts with kb_name and channel_id filtering.
    Uses the new scroll_kb_chunks API with proper pagination and channel isolation.
    """
    kb_name = state.get("kb_name")
    channel_id = state.get("channel_id")
    
    # P0 Fix: Enforce channel_id for multi-tenant isolation
    if not channel_id:
        raise ValueError("channel_id is required for GraphRAG processing to ensure tenant isolation")
    
    if not kb_name:
        raise ValueError("kb_name is required for GraphRAG processing")
    
    # Use scroll API for memory-efficient iteration
    max_chunks = int(os.environ.get("GRAPHRAG_MAX_CHUNKS", "50000"))
    all_chunks: list[str] = []
    
    try:
        for batch in scroll_kb_chunks(
            kb_name=kb_name,
            channel_id=channel_id,
            batch_size=1000,
            max_chunks=max_chunks,
        ):
            for chunk in batch:
                content = str(chunk.get("content") or "").strip()
                if content:
                    all_chunks.append(content)
            
            # Safety check
            if len(all_chunks) >= max_chunks:
                break
                
    except Exception as e:
        # Log error but continue with what we have
        import logging
        logging.getLogger(__name__).warning(f"Error collecting texts for GraphRAG: {e}")
    
    state["chunks"] = all_chunks
    return state


async def _extract_one(gw: LLMGateway, text: str) -> dict[str, Any]:
    prompt = (
        "抽取文本中的实体(人名/组织/地理/事件/类别)与关系, 返回JSON: "
        '{"entities":[{"name":...,"type":...,"desc":...}],'
        '"relations":[{"src":...,"tgt":...,"desc":...,"keywords":[]}]}'
    )
    try:
        out = await gw.chat(prompt=prompt, context=text)
        data = json.loads(out) if out else {}
    except Exception:
        data = {}
    return {
        "entities": list(data.get("entities") or []),
        "relations": list(data.get("relations") or []),
    }


async def extract_graph(state: GraphDeepState) -> GraphDeepState:
    gw = LLMGateway(provider=(settings.llm_provider or "dashscope"))
    items = state.get("chunks") or []
    concurrency = int(os.environ.get("GRAPH_DEEP_MAX_CONCURRENCY", "8"))
    sem = asyncio.Semaphore(max(1, concurrency))

    async def run(text: str):
        async with sem:
            return await _extract_one(gw, text)

    tasks = [run(t) for t in items]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for r in results:
        if isinstance(r, Exception):
            continue
        for e in r.get("entities", []):
            nm = str(e.get("name") or "").strip()
            if not nm:
                continue
            cur = nodes.setdefault(
                nm, {"entity_name": nm, "entity_type": e.get("type"), "description": ""}
            )
            desc = str(e.get("desc") or "")
            if desc:
                cur["description"] = (
                    (cur.get("description") or "") + ("\n" if cur.get("description") else "") + desc
                )
        for rel in r.get("relations", []):
            src = str(rel.get("src") or "").strip()
            tgt = str(rel.get("tgt") or "").strip()
            if not src or not tgt:
                continue
            k = (src, tgt) if src <= tgt else (tgt, src)
            cur = edges.setdefault(
                k, {"src_id": k[0], "tgt_id": k[1], "description": "", "keywords": [], "weight": 0}
            )
            desc = str(rel.get("desc") or "").strip()
            kws = [str(x) for x in (rel.get("keywords") or [])]
            if desc:
                cur["description"] = (
                    (cur.get("description") or "") + ("\n" if cur.get("description") else "") + desc
                )
            cur["keywords"] = sorted(set((cur.get("keywords") or []) + kws))
            cur["weight"] = int(cur.get("weight") or 0) + 1
    state["graph"] = {"nodes": list(nodes.values()), "edges": list(edges.values())}
    return state


async def detect_communities(state: GraphDeepState) -> GraphDeepState:
    """
    Detect communities using Louvain algorithm.

    Requires networkx with community detection support.
    Falls back gracefully if not available.
    """
    graph_data = state.get("graph", {})
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    if not nodes or not edges:
        state["communities"] = []
        return state

    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError:
        # Fallback: treat all nodes as one community
        state["communities"] = [
            {
                "id": 0,
                "level": 0,
                "members": [n["entity_name"] for n in nodes],
                "size": len(nodes),
                "summary": "",
            }
        ]
        return state

    # Build networkx graph
    G = nx.Graph()

    # Add nodes with attributes
    for node in nodes:
        G.add_node(
            node["entity_name"],
            entity_type=node.get("entity_type"),
            description=node.get("description", ""),
        )

    # Add edges with weights
    for edge in edges:
        G.add_edge(
            edge["src_id"],
            edge["tgt_id"],
            weight=edge.get("weight", 1),
            description=edge.get("description", ""),
        )

    # Detect communities with Louvain
    try:
        resolution = float(os.environ.get("LOUVAIN_RESOLUTION", "1.0"))
        communities = louvain_communities(G, weight="weight", resolution=resolution, seed=42)

        community_list = []
        for idx, members in enumerate(communities):
            member_list = sorted(list(members))

            # Generate community summary (top entities by degree)
            subgraph = G.subgraph(members)
            degrees = dict(subgraph.degree())
            top_entities = sorted(degrees.keys(), key=lambda x: degrees[x], reverse=True)[:5]

            community_list.append(
                {
                    "id": idx,
                    "level": 1,  # Single-level Louvain
                    "members": member_list,
                    "size": len(members),
                    "top_entities": top_entities,
                    "internal_edges": subgraph.number_of_edges(),
                    "summary": "",  # Can be filled by LLM later
                }
            )

        state["communities"] = community_list

    except Exception:
        # Fallback: single community
        state["communities"] = [
            {
                "id": 0,
                "level": 0,
                "members": [n["entity_name"] for n in nodes],
                "size": len(nodes),
                "summary": "",
            }
        ]

    return state


async def summarize_communities(state: GraphDeepState) -> GraphDeepState:
    """
    Generate LLM summaries for each community.

    Uses top entities and internal relationships to create descriptive summaries.
    """
    communities = state.get("communities", [])
    if not communities:
        return state

    # Only summarize if enabled
    if os.environ.get("GRAPH_COMMUNITY_SUMMARIZE", "").lower() not in ("true", "1"):
        return state

    gw = LLMGateway(provider=(settings.llm_provider or "dashscope"))
    graph_data = state.get("graph", {})
    nodes_map = {n["entity_name"]: n for n in graph_data.get("nodes", [])}

    async def summarize_one(community: dict) -> dict:
        members = community.get("members", [])[:10]  # Limit for prompt
        top_entities = community.get("top_entities", [])[:5]

        # Build context from entities
        entity_info = []
        for name in top_entities:
            node = nodes_map.get(name, {})
            desc = node.get("description", "")[:200]
            entity_info.append(f"- {name} ({node.get('entity_type', 'unknown')}): {desc}")

        prompt = f"""Summarize this knowledge graph community in 1-2 sentences.

Top entities:
{chr(10).join(entity_info)}

Total members: {len(members)}

Summary:"""

        try:
            summary = await gw.chat(prompt)
            community["summary"] = summary.strip()
        except Exception:
            community["summary"] = (
                f"Community with {len(members)} entities including {', '.join(top_entities[:3])}"
            )

        return community

    # Summarize communities concurrently
    sem = asyncio.Semaphore(4)

    async def run(c):
        async with sem:
            return await summarize_one(c)

    summarized = await asyncio.gather(*[run(c) for c in communities], return_exceptions=True)
    state["communities"] = [c for c in summarized if isinstance(c, dict)]

    return state


async def store_graph(state: GraphDeepState) -> GraphDeepState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "knowledge_graphs")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")

    # Store graph
    graph_path = os.path.join(out_dir, f"{name}.graph.deep.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(state.get("graph") or {}, f, ensure_ascii=False, indent=2)

    # Store communities
    communities_path = os.path.join(out_dir, f"{name}.communities.json")
    with open(communities_path, "w", encoding="utf-8") as f:
        json.dump(state.get("communities") or [], f, ensure_ascii=False, indent=2)

    meta = state.get("meta") or {}
    meta["graph_path_deep"] = graph_path
    meta["communities_path"] = communities_path
    meta["node_count"] = len((state.get("graph") or {}).get("nodes", []))
    meta["edge_count"] = len((state.get("graph") or {}).get("edges", []))
    meta["community_count"] = len(state.get("communities") or [])
    state["meta"] = meta
    return state


def create_graphrag_deep_graph():
    g = StateGraph(GraphDeepState)
    g.add_node("collect_texts", collect_texts)
    g.add_node("extract_graph", extract_graph)
    g.add_node("detect_communities", detect_communities)
    g.add_node("summarize_communities", summarize_communities)
    g.add_node("store_graph", store_graph)

    g.set_entry_point("collect_texts")
    g.add_edge("collect_texts", "extract_graph")
    g.add_edge("extract_graph", "detect_communities")
    g.add_edge("detect_communities", "summarize_communities")
    g.add_edge("summarize_communities", "store_graph")

    mem = MemorySaver()
    return g.compile(checkpointer=mem)
