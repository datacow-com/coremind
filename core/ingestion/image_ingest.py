import os
import base64
from typing import List, Optional, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


class ImageIngestState(TypedDict):
    file_paths: List[str]
    md: Optional[str]
    meta: Dict[str, Any]


async def images_to_md(state: ImageIngestState) -> ImageIngestState:
    from core.llm.gateway import LLMGateway
    import os
    gw = LLMGateway(provider=os.environ.get("VISION_PROVIDER", "dashscope"))
    prompt = "Extract structured Markdown with headings, lists, tables and preserve reading order."
    parts: List[str] = []
    for fp in state.get("file_paths", []):
        try:
            with open(fp, "rb") as f:
                ib = f.read()
            md = await gw.vision_markdown(image_bytes=ib, prompt=prompt)
            if md:
                parts.append(md)
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

