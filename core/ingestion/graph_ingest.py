import logging
import os
from typing import Any

import fitz
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from server.config import settings


class IngestState(TypedDict):
    file_path: str
    images: list[str]
    md: str | None
    meta: dict[str, Any]


async def pdf_to_images(state: IngestState) -> IngestState:
    fp = state["file_path"]
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    imgs: list[str] = []
    try:
        doc = fitz.open(fp)
        for i in range(len(doc)):
            pix = doc[i].get_pixmap()
            p = os.path.join(out_dir, f"{os.path.basename(fp)}_{i}.png")
            pix.save(p)
            imgs.append(p)
    except Exception as e:
        logging.exception("pdf_to_images failed", extra={"file_path": fp})
        meta = state.get("meta", {})
        meta["error"] = str(e)
        meta["file_path"] = fp
        state["meta"] = meta
    state["images"] = imgs
    return state


async def vlm_extract_md(state: IngestState) -> IngestState:
    from core.llm.gateway import LLMGateway

    gw = LLMGateway(provider=settings.vision_provider or "dashscope")
    md: str | None = None
    if state.get("images"):
        prompt = (
            "Extract structured Markdown with headings, lists, tables and preserve reading order."
        )
        parts: list[str] = []
        for img in state["images"]:
            try:
                with open(img, "rb") as f:
                    ib = f.read()
                out = await gw.vision_markdown(image_bytes=ib, prompt=prompt)
                if out:
                    parts.append(out)
            except Exception:
                continue
        if parts:
            md = "\n\n".join(parts)
    if not md and not state.get("images"):
        base_name = os.path.basename(state.get("file_path", "document.pdf"))
        err = state.get("meta", {}).get("error")
        md = f"# {base_name}\n\nExtraction failed. Placeholder generated.\n\nError: {err or 'unknown'}\n"
    state["md"] = md or "# Document\n"
    return state


async def md_postprocess(state: IngestState) -> IngestState:
    s = state.get("md") or ""
    s = s.replace("\r\n", "\n")
    state["md"] = s
    return state


async def store_md(state: IngestState) -> IngestState:
    base_dir = settings.uploads_dir_resolved
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state["file_path"]))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    return state


def create_ingest_graph():
    g = StateGraph(IngestState)
    g.add_node("pdf_to_images", pdf_to_images)
    g.add_node("vlm_extract_md", vlm_extract_md)
    g.add_node("md_postprocess", md_postprocess)
    g.add_node("store_md", store_md)
    g.set_entry_point("pdf_to_images")
    g.add_edge("pdf_to_images", "vlm_extract_md")
    g.add_edge("vlm_extract_md", "md_postprocess")
    g.add_edge("md_postprocess", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)
