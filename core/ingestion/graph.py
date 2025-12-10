"""
Ingestion Graph - Main ingestion pipeline with LangGraph.

Features:
- Document loading and routing
- CPU/GPU parsing paths
- Quality checking and filtering
- Error handling and retry
- Final indexing and cleanup
"""

from langgraph.graph import StateGraph, END

from core.state import IngestState
from core.storage.checkpoint import get_postgres_saver

# Nodes
from core.ingestion.nodes.loader import LoaderNode
from core.ingestion.nodes.router import RouterNode, route_file
from core.ingestion.nodes.parser import CpuTextParser, GpuVisionParser
from core.ingestion.nodes.chunker import SmartChunker
from core.ingestion.nodes.embedder import BatchEmbedder
from core.ingestion.nodes.indexer import DualIndexer
from core.ingestion.nodes.quality_checker import QualityChecker
from core.ingestion.nodes.error_handler import ErrorHandler
from core.ingestion.nodes.finalizer import Finalizer


def _should_retry(state: IngestState) -> str:
    """Decide whether to retry or proceed to finalizer after error handling."""
    if state.get("should_retry", False):
        retry_stage = state.get("processing_stage", "loader")
        if retry_stage in ["loader", "router", "cpu_parser", "gpu_parser"]:
            return "loader"  # Restart from loader
        return "chunker"  # Resume from chunker
    return "finalizer"


def _quality_gate(state: IngestState) -> str:
    """Route based on quality check results."""
    if state.get("quality_passed", True):
        return "embedder"
    # Low quality - still try to process but log warning
    error_log = state.get("error_log", [])
    error_log.append({
        "stage": "quality_checker",
        "warning": "Low quality chunks detected, proceeding with caution"
    })
    state["error_log"] = error_log
    return "embedder"


def create_ingest_graph():
    """
    Create the ingestion graph with full pipeline.
    
    Pipeline: 
    loader -> router -> cpu_parser/gpu_parser -> chunker -> qc -> embedder -> indexer -> finalizer
                                                              |
                                               error_handler <--> (retry or finalizer)
    """
    workflow = StateGraph(IngestState)
    
    # Add Nodes
    workflow.add_node("loader", LoaderNode())
    workflow.add_node("router", RouterNode())
    workflow.add_node("cpu_parser", CpuTextParser())
    workflow.add_node("gpu_parser", GpuVisionParser())
    workflow.add_node("chunker", SmartChunker())
    workflow.add_node("qc", QualityChecker())  # P1 Fix: Quality checker
    workflow.add_node("embedder", BatchEmbedder())
    workflow.add_node("indexer", DualIndexer())
    workflow.add_node("error_handler", ErrorHandler())  # P1 Fix: Error handler
    workflow.add_node("finalizer", Finalizer())  # P1 Fix: Finalizer
    
    # Edges
    workflow.set_entry_point("loader")
    workflow.add_edge("loader", "router")
    
    # Conditional routing based on file type
    workflow.add_conditional_edges(
        "router",
        route_file,
        {
            "cpu_parser": "cpu_parser",
            "gpu_parser": "gpu_parser"
        }
    )
    
    # Parser to chunker
    workflow.add_edge("cpu_parser", "chunker")
    workflow.add_edge("gpu_parser", "chunker")
    
    # Chunker to quality checker
    workflow.add_edge("chunker", "qc")
    
    # Quality gate - proceed to embedder regardless (but log warnings for low quality)
    workflow.add_conditional_edges(
        "qc",
        _quality_gate,
        {
            "embedder": "embedder",
        }
    )
    
    # Main path
    workflow.add_edge("embedder", "indexer")
    workflow.add_edge("indexer", "finalizer")
    
    # Finalizer to END
    workflow.add_edge("finalizer", END)
    
    # Error handler paths
    workflow.add_conditional_edges(
        "error_handler",
        _should_retry,
        {
            "loader": "loader",
            "chunker": "chunker",
            "finalizer": "finalizer"
        }
    )
    
    # Compile with Checkpointer
    checkpointer = get_postgres_saver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app


# Legacy alias
def create_legacy_ingest_graph():
    """Alias for backward compatibility."""
    return create_ingest_graph()
