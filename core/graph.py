import os
from langgraph.graph import StateGraph, END
from core.state import RAGState
from core.nodes.route import route
from core.nodes.ingest import ingest
from core.nodes.retrieve import retrieve
from core.nodes.rerank import rerank
from core.nodes.grade import grade
from core.nodes.web_search import web_search
from core.nodes.generate import generate
from core.nodes.hallucination import hallucination
try:
    from langgraph.checkpoint.postgres import PostgresSaver
except Exception:
    PostgresSaver = None


def create_graph():
    graph = StateGraph(RAGState)

    graph.add_node("route", route)
    graph.add_node("ingest", ingest)
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
            return "generate"
        if intent == "web_search":
            return "web_search"
        # execute 暂时路由到 web_search 或后续工具节点
        if intent == "execute":
            return "web_search"
        return "retrieve"

    graph.add_conditional_edges("route", route_router)
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "grade")

    def grade_router(state: RAGState) -> str:
        return "web_search" if state.get("web_search_needed") else "generate"

    graph.add_conditional_edges("grade", grade_router)

    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", "hallucination")
    graph.add_edge("hallucination", END)

    checkpointer = None
    if PostgresSaver is not None:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            try:
                checkpointer = PostgresSaver.from_conn_string(db_url)
            except Exception:
                checkpointer = None
    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
