from typing import Callable
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

    graph.add_edge("route", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "grade")

    def grade_router(state: RAGState) -> str:
        return "web_search" if state.get("web_search_needed") else "generate"

    graph.add_conditional_edges("grade", grade_router)

    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", "hallucination")
    graph.add_edge("hallucination", END)

    return graph.compile()

