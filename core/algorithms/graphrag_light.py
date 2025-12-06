import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.storage.index_router import list_all_meta
from server.config import settings


class GraphState(TypedDict):
    kb_name: str
    method: str
    chunks: list[dict[str, Any]]
    graph: dict[str, Any]
    meta: dict[str, Any]


async def collect_chunks(state: GraphState) -> GraphState:
    kb = state.get("kb_name")
    ms = list_all_meta()
    state["chunks"] = [m for m in ms if not kb or True]
    return state


async def build_graph(state: GraphState) -> GraphState:
    items = state.get("chunks", [])
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    for m in items:
        txt = str(m.get("content") or "")
        did = str(m.get("doc_id") or "")
        key = f"{did}:{int(m.get("page_num") or 0)}:{int(m.get("chunk_index") or 0)}"
        ents = []
        rels = []
        try:
            from core.llm.gateway import LLMGateway

            gw = LLMGateway()
            prompt = (
                "提取文本中的实体(人名/组织/地理/事件/类别)与关系, 用JSON返回, 格式: "
                '{"entities":[{"name":...,"type":...,"desc":...}],'
                '"relations":[{"src":...,"tgt":...,"desc":...,"keywords":[]}]}'
            )
            out = await gw.chat(prompt=prompt, context=txt)
            data = json.loads(out) if out else {}
            ents = list(data.get("entities") or [])
            rels = list(data.get("relations") or [])
        except Exception:
            ents = []
            rels = []
        for e in ents:
            nm = str(e.get("name") or "").strip()
            if not nm:
                continue
            cur = nodes.setdefault(
                nm,
                {
                    "entity_name": nm,
                    "entity_type": e.get("type"),
                    "description": "",
                    "source_id": [],
                },
            )
            desc = str(e.get("desc") or "").strip()
            if desc:
                cur["description"] = (
                    (cur.get("description") or "") + ("\n" if cur.get("description") else "") + desc
                )
            cur["source_id"] = sorted(set((cur.get("source_id") or []) + [key]))
        for r in rels:
            src = str(r.get("src") or "").strip()
            tgt = str(r.get("tgt") or "").strip()
            if not src or not tgt:
                continue
            k = (src, tgt) if src <= tgt else (tgt, src)
            cur = edges.setdefault(
                k,
                {
                    "src_id": k[0],
                    "tgt_id": k[1],
                    "description": "",
                    "keywords": [],
                    "weight": 0,
                    "source_id": [],
                },
            )
            desc = str(r.get("desc") or "").strip()
            kws = list(r.get("keywords") or [])
            if desc:
                cur["description"] = (
                    (cur.get("description") or "") + ("\n" if cur.get("description") else "") + desc
                )
            cur["keywords"] = sorted(set((cur.get("keywords") or []) + [str(x) for x in kws]))
            cur["weight"] = int(cur.get("weight") or 0) + 1
            cur["source_id"] = sorted(set((cur.get("source_id") or []) + [key]))
    state["graph"] = {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
    return state


async def store_graph(state: GraphState) -> GraphState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "knowledge_graphs")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.graph.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.get("graph") or {}, f, ensure_ascii=False, indent=2)
    meta = state.get("meta", {})
    meta["graph_path"] = path
    state["meta"] = meta
    return state


def create_graphrag_light_graph():
    g = StateGraph(GraphState)
    g.add_node("collect_chunks", collect_chunks)
    g.add_node("build_graph", build_graph)
    g.add_node("store_graph", store_graph)
    g.set_entry_point("collect_chunks")
    g.add_edge("collect_chunks", "build_graph")
    g.add_edge("build_graph", "store_graph")
    mem = MemorySaver()
    return g.compile(checkpointer=mem)
