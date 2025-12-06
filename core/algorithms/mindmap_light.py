import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.storage.index_router import list_all_meta
from server.config import settings


class MindState(TypedDict):
    kb_name: str
    outline: dict[str, Any]
    meta: dict[str, Any]


async def collect_chunks(state: MindState) -> MindState:
    state["meta"] = state.get("meta") or {}
    state["meta"]["chunks"] = list_all_meta()
    return state


async def build_outline(state: MindState) -> MindState:
    ms = state.get("meta", {}).get("chunks") or []
    parts = {}
    for m in ms:
        did = str(m.get("doc_id") or "")
        arr = parts.setdefault(did, [])
        arr.append(str(m.get("content") or ""))
    outline = {"title": state.get("kb_name") or "KB", "children": []}
    from core.llm.gateway import LLMGateway

    gw = LLMGateway()
    for did, arr in parts.items():
        ctx = "\n\n".join(arr[:50])
        try:
            title = await gw.chat(prompt="为此文档生成5个词以内的主题名称", context=ctx)
            summary = await gw.chat(prompt="生成该文档的简要摘要(200字)", context=ctx)
        except Exception:
            title = did
            summary = ""
        outline["children"].append({"title": title.strip() or did, "summary": summary})
    state["outline"] = outline
    return state


async def store_outline(state: MindState) -> MindState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "mindmap")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.mindmap.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.get("outline") or {}, f, ensure_ascii=False, indent=2)
    meta = state.get("meta", {})
    meta["mindmap_path"] = path
    state["meta"] = meta
    return state


def create_mindmap_light_graph():
    g = StateGraph(MindState)
    g.add_node("collect_chunks", collect_chunks)
    g.add_node("build_outline", build_outline)
    g.add_node("store_outline", store_outline)
    g.set_entry_point("collect_chunks")
    g.add_edge("collect_chunks", "build_outline")
    g.add_edge("build_outline", "store_outline")
    mem = MemorySaver()
    return g.compile(checkpointer=mem)
