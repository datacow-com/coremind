import json
import os
import random
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.embedding.provider_embedder import Embedder
from core.storage.index_router import list_all_meta
from server.config import settings


class RaptorState(TypedDict):
    kb_name: str
    scope: str
    prompt: str
    max_tokens: int
    threshold: float
    max_clusters: int
    seed: int
    file_id: str | None
    chunks: list[dict[str, Any]]
    layers: list[list[int]]
    summaries: list[dict[str, Any]]
    meta: dict[str, Any]


async def collect_chunks(state: RaptorState) -> RaptorState:
    ms = list_all_meta()
    state["chunks"] = ms
    return state


def _embed(texts: list[str]) -> list[list[float]]:
    emb = Embedder(dim=256)
    return [emb.embed(t) for t in texts]


async def cluster_and_summarize(state: RaptorState) -> RaptorState:
    items = state.get("chunks", [])
    texts = [str(m.get("content") or "") for m in items]
    vecs = _embed(texts)
    n = len(vecs)
    if n <= 1:
        state["summaries"] = []
        state["layers"] = [(list(range(n)))]
        return state
    rnd = int(state.get("seed") or 0)
    random.seed(rnd)
    k = max(2, min(int(state.get("max_clusters") or 8), n))
    idxs = list(range(n))
    random.shuffle(idxs)
    groups: list[list[int]] = [[] for _ in range(k)]
    for i, ix in enumerate(idxs):
        groups[i % k].append(ix)
    from core.llm.gateway import LLMGateway

    gw = LLMGateway()
    prompt = state.get("prompt") or "对下面文本做高度抽象总结，输出不超过300字。"
    summaries: list[dict[str, Any]] = []
    for g in groups:
        parts = [texts[i] for i in g]
        ctx = "\n\n".join(parts)
        try:
            out = await gw.chat(prompt=prompt, context=ctx)
        except Exception:
            out = ""
        summaries.append({"summary": out, "indices": g})
    state["summaries"] = summaries
    state["layers"] = [list(range(n)), [i for i in range(len(summaries))]]
    return state


async def store_hierarchy(state: RaptorState) -> RaptorState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "raptor")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.raptor.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"layers": state.get("layers"), "summaries": state.get("summaries")},
            f,
            ensure_ascii=False,
            indent=2,
        )
    meta = state.get("meta", {})
    meta["raptor_path"] = path
    state["meta"] = meta
    return state


def create_raptor_light_graph():
    g = StateGraph(RaptorState)
    g.add_node("collect_chunks", collect_chunks)
    g.add_node("cluster_and_summarize", cluster_and_summarize)
    g.add_node("store_hierarchy", store_hierarchy)
    g.set_entry_point("collect_chunks")
    g.add_edge("collect_chunks", "cluster_and_summarize")
    g.add_edge("cluster_and_summarize", "store_hierarchy")
    mem = MemorySaver()
    return g.compile(checkpointer=mem)
