import os
from typing import Any

from langgraph.graph import END, StateGraph

from core.nodes.generate import generate
from core.nodes.grade import grade
from core.nodes.hallucination import hallucination
from core.nodes.rerank import rerank
from core.nodes.retrieve import retrieve
from core.nodes.route import route
from core.nodes.web_search import web_search
from core.state import RAGState

_PostgresSaver: Any | None = None
try:
    from langgraph.checkpoint.postgres import PostgresSaver as _PostgresSaver
except Exception:
    _PostgresSaver = None


def create_graph():
    graph = StateGraph(RAGState)

    graph.add_node("route", route)
    graph.add_node("retrieve", retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("grade", grade)
    graph.add_node("web_search", web_search)
    graph.add_node("generate", generate)
    graph.add_node("hallucination", hallucination)

    graph.set_entry_point("route")

    def route_router(state: RAGState) -> str:
        intent = (state.get("intent") or "qa").lower()
        if intent == "summarize":
            return "retrieve"
        if intent == "web_search":
            return "web_search"
        if intent == "execute":
            return "retrieve"
        return "retrieve"

    graph.add_conditional_edges("route", route_router)
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "grade")

    def grade_router(state: RAGState) -> str:
        intent = (state.get("intent") or "qa").lower()
        if state.get("web_search_needed"):
            return "web_search"
        if intent == "execute":
            return "execute"
        if intent == "summarize":
            return "generate"
        return "generate"

    graph.add_conditional_edges("grade", grade_router)

    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", "hallucination")
    graph.add_node("execute", __import__("core.nodes.execute", fromlist=["execute"]).execute)
    graph.add_edge("execute", "hallucination")
    graph.add_edge("hallucination", END)

    checkpointer = None
    if _PostgresSaver is not None:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            try:
                checkpointer = _PostgresSaver.from_conn_string(db_url)
            except Exception:
                checkpointer = None
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
