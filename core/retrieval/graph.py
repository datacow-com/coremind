from langgraph.graph import StateGraph, END
from core.state import RetrievalState

# Nodes
from core.retrieval.nodes.preprocessor import QueryPreProcessor
from core.retrieval.nodes.retriever import HybridRetriever
from core.retrieval.nodes.reranker import CrossEncoderReranker
from core.retrieval.nodes.generator import CitationGenerator

def create_qa_graph():
    workflow = StateGraph(RetrievalState)
    
    workflow.add_node("preprocessor", QueryPreProcessor())
    workflow.add_node("retriever", HybridRetriever())
    workflow.add_node("reranker", CrossEncoderReranker())
    workflow.add_node("generator", CitationGenerator())
    
    workflow.set_entry_point("preprocessor")
    
    workflow.add_edge("preprocessor", "retriever")
    workflow.add_edge("retriever", "reranker")
    
    def check_relevance(state):
        if state.get('is_relevant', False):
            return "generator"
        else:
            # Loop logic: if loop_count < 2 -> preprocessor (rewrite)
            # For MVP, simple end or direct to generator with "not found"
            loop = state.get('loop_count', 0)
            if loop < 1:
                state['loop_count'] = loop + 1
                return "preprocessor"
            return "generator"

    workflow.add_conditional_edges(
        "reranker",
        check_relevance,
        {
            "generator": "generator",
            "preprocessor": "preprocessor"
        }
    )
    
    workflow.add_edge("generator", END)
    
    return workflow.compile()

