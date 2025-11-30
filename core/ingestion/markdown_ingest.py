import os
from typing import Optional, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


class MarkdownIngestState(TypedDict):
    md: Optional[str]
    file_path: Optional[str]
    meta: Dict[str, Any]


async def read_or_pass(state: MarkdownIngestState) -> MarkdownIngestState:
    fp = state.get("file_path")
    if fp and os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                state["md"] = f.read()
        except Exception:
            state["md"] = state.get("md") or ""
    return state


async def store_md(state: MarkdownIngestState) -> MarkdownIngestState:
    base_dir = os.environ.get("UPLOADS_DIR", "/app/uploads")
    out_dir = os.path.join(base_dir, "ingest")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(state.get("file_path") or "document.md"))[0]
    out_md = os.path.join(out_dir, f"{stem}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(state.get("md") or "")
    m = state.get("meta", {})
    m["md_path"] = out_md
    state["meta"] = m
    return state


def create_markdown_ingest_graph():
    g = StateGraph(MarkdownIngestState)
    g.add_node("read_or_pass", read_or_pass)
    g.add_node("store_md", store_md)
    g.set_entry_point("read_or_pass")
    g.add_edge("read_or_pass", "store_md")
    memory = MemorySaver()
    return g.compile(checkpointer=memory)

