import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict


class ImageIngestState(TypedDict):
    file_paths: list[str]
    md: str | None
    meta: dict[str, Any]


async def images_to_md(state: ImageIngestState) -> ImageIngestState:
    import os

    from core.embedding.registry import get_embedder
    from core.llm.gateway import LLMGateway
    from core.storage.index_router import add as index_add

    gw = LLMGateway(model=os.environ.get("VISION_MODEL"))
    prompt = "Extract structured Markdown with headings, lists, tables and preserve reading order."
    parts: list[str] = []
    for fp in state.get("file_paths", []):
        try:
            with open(fp, "rb") as f:
                ib = f.read()
            md = await gw.vision_markdown(image_bytes=ib, prompt=prompt)
            if md:
                parts.append(md)
                # write chunks to index
                paras = [p.strip() for p in md.split("\n\n") if p.strip()]
                emb = get_embedder(model_name=os.environ.get("EMBEDDING_MODEL"))
                from core.storage.keyword_index import get_keyword_index

                kw = get_keyword_index()
                if paras:
                    try:
                        vecs = await emb.embed_batch(paras) if hasattr(emb, "embed_batch") else None
                    except Exception:
                        vecs = None
                    for i, chunk in enumerate(paras):
                        import asyncio

                        vec = None
                        if vecs is not None and len(vecs) > i:
                            vec = vecs[i]
                        else:
                            vec = await asyncio.to_thread(emb.embed, chunk)
                        meta = {
                            "id": f"{fp}-chunk-{i}",
                            "content": chunk,
                            "page_num": 1,
                            "doc_id": fp or "image",
                            "chunk_index": i,
                            "metadata": {"type": "image", "bbox": None, "confidence": 0.0},
                        }
                        index_add(vec, meta)
                        kw.add(chunk, meta)
        except Exception:
            continue
    state["md"] = "\n\n".join(parts) if parts else (state.get("md") or "")
    return state


async def store_md(state: ImageIngestState) -> ImageIngestState:
    base_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_paths", ["images"])[0]))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    return state


def create_image_ingest_graph():
    g = StateGraph(ImageIngestState)
    g.add_node("images_to_md", images_to_md)
    g.add_node("store_md", store_md)
    g.set_entry_point("images_to_md")
    g.add_edge("images_to_md", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
