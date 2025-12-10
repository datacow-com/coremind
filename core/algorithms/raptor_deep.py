import asyncio
import json
import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from core.embedding.provider_embedder import Embedder
from core.llm.gateway import LLMGateway
from core.storage.index_router import list_all_meta
from server.config import settings


class RaptorDeepState(TypedDict):
    kb_name: str
    channel_id: str  # P0 Fix: Added for multi-tenant isolation
    prompt: str
    max_token: int
    threshold: float
    max_cluster: int
    random_seed: int
    chunks: list[str]
    layers: list[list[int]]
    summaries: list[dict[str, Any]]
    meta: dict[str, Any]


async def collect_texts(state: RaptorDeepState) -> RaptorDeepState:
    """
    P0 Fix: Collect texts with kb_name and channel_id filtering.
    Uses pagination to avoid OOM on large datasets.
    """
    from core.storage.index_router import list_page_meta
    
    kb_name = state.get("kb_name")
    channel_id = state.get("channel_id", "default")
    
    # Pagination to avoid OOM
    all_chunks: list[str] = []
    offset = 0
    page_size = 1000  # Process in batches
    max_chunks = 50000  # Safety limit
    
    while len(all_chunks) < max_chunks:
        try:
            # Get page with filtering
            page = list_page_meta(
                kb_name=kb_name,
                channel_id=channel_id,
                offset=offset,
                limit=page_size
            )
        except TypeError:
            # Fallback if list_page_meta doesn't support all params yet
            ms = list_all_meta()
            # Manual filtering
            page = [
                m for m in ms 
                if (not kb_name or m.get("kb_name") == kb_name) and
                   (not channel_id or channel_id == "default" or m.get("channel_id") == channel_id)
            ][offset:offset + page_size]
        
        if not page:
            break
            
        for m in page:
            content = str(m.get("content") or "").strip()
            if content:
                all_chunks.append(content)
        
        offset += page_size
        
        # Safety check
        if len(page) < page_size:
            break
    
    state["chunks"] = all_chunks
    return state


def _cluster(texts: list[str], k: int, seed: int) -> list[list[int]]:
    emb = Embedder(dim=256)
    vecs = [emb.embed(t) for t in texts]
    n = len(vecs)
    if n == 0:
        return []
    import random

    random.seed(seed)
    centers = random.sample(range(n), min(k, n))
    groups: list[list[int]] = [[] for _ in centers]
    for i, v in enumerate(vecs):
        best = 0
        best_sim = -1e9
        for ci, cidx in enumerate(centers):
            cv = vecs[cidx]
            sim = sum(a * b for a, b in zip(v, cv, strict=False))
            if sim > best_sim:
                best_sim = sim
                best = ci
        groups[best].append(i)
    return groups


async def summarize_groups(state: RaptorDeepState) -> RaptorDeepState:
    texts = state.get("chunks") or []
    k = max(2, min(int(state.get("max_cluster") or 8), max(1, len(texts))))
    groups = _cluster(texts, k, int(state.get("random_seed") or 0))
    gw = LLMGateway(provider=(settings.llm_provider or "dashscope"))
    prompt = state.get("prompt") or "对下面文本做层级摘要，输出不超过300字。"

    async def run(ctx: str):
        try:
            return await gw.chat(prompt=prompt, context=ctx)
        except Exception:
            return ""

    concurrency = int(os.environ.get("RAPTOR_DEEP_MAX_CONCURRENCY", "6"))
    sem = asyncio.Semaphore(max(1, concurrency))
    tasks = []
    for g in groups:
        ctx = "\n\n".join([texts[i] for i in g])

        async def one(c=ctx):
            async with sem:
                return await run(c)

        tasks.append(one())
    outs = await asyncio.gather(*tasks, return_exceptions=True)
    summaries = []
    for g, s in zip(groups, outs, strict=False):
        if isinstance(s, Exception):
            s = ""
        summaries.append({"summary": s, "indices": g})
    state["summaries"] = summaries
    state["layers"] = [list(range(len(texts))), list(range(len(summaries)))]
    return state


async def store_raptor(state: RaptorDeepState) -> RaptorDeepState:
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "raptor")
    os.makedirs(out_dir, exist_ok=True)
    name = str(state.get("kb_name") or "default")
    path = os.path.join(out_dir, f"{name}.raptor.deep.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"layers": state.get("layers"), "summaries": state.get("summaries")},
            f,
            ensure_ascii=False,
            indent=2,
        )
    meta = state.get("meta") or {}
    meta["raptor_path_deep"] = path
    meta["summary_count"] = len(state.get("summaries") or [])
    state["meta"] = meta
    return state


def create_raptor_deep_graph():
    g = StateGraph(RaptorDeepState)
    g.add_node("collect_texts", collect_texts)
    g.add_node("summarize_groups", summarize_groups)
    g.add_node("store_raptor", store_raptor)
    g.set_entry_point("collect_texts")
    g.add_edge("collect_texts", "summarize_groups")
    g.add_edge("summarize_groups", "store_raptor")
    mem = MemorySaver()
    return g.compile(checkpointer=mem)
