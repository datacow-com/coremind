import asyncio
import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.llm.gateway import LLMGateway
from core.storage.index_router import list_all_meta
from server.config import settings


class GraphDeepState(TypedDict):
    kb_name: str
    language: str | None
    entity_types: list[str] | None
    chunks: list[str]
    graph: dict[str, Any]
    meta: dict[str, Any]


async def collect_texts(state: GraphDeepState) -> GraphDeepState:
    ms = list_all_meta()
    state["chunks"] = [
        str(m.get("content") or "") for m in ms if str(m.get("content") or "").strip()
    ]
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


async def store_graph(state: GraphDeepState) -> GraphDeepState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "knowledge_graphs")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.graph.deep.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.get("graph") or {}, f, ensure_ascii=False, indent=2)
    meta = state.get("meta") or {}
    meta["graph_path_deep"] = path
    meta["node_count"] = len((state.get("graph") or {}).get("nodes", []))
    meta["edge_count"] = len((state.get("graph") or {}).get("edges", []))
    state["meta"] = meta
    return state


def create_graphrag_deep_graph():
    g = StateGraph(GraphDeepState)
    g.add_node("collect_texts", collect_texts)
    g.add_node("extract_graph", extract_graph)
    g.add_node("store_graph", store_graph)
    g.set_entry_point("collect_texts")
    g.add_edge("collect_texts", "extract_graph")
    g.add_edge("extract_graph", "store_graph")
    mem = MemorySaver()
    return g.compile(checkpointer=mem)
