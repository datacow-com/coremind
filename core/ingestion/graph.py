"""
Ingestion Graph - Main ingestion pipeline with LangGraph.

Features:
- Document loading and routing
- CPU/GPU parsing paths
- Quality checking and filtering
- Error handling and retry
- Final indexing and cleanup

P1 Fix: Lazy imports to avoid gRPC mutex lock on module import.
"""

# Lazy imports to avoid gRPC/protobuf mutex lock issues
# LangGraph may internally use gRPC which can cause mutex blocking on import


def _lazy_import_langgraph():
    """Lazy import LangGraph to avoid gRPC mutex lock on module import."""
    try:
        from langgraph.graph import StateGraph, END
        return StateGraph, END
    except ImportError as e:
        raise ImportError(f"LangGraph not installed: {e}")


def _lazy_import_nodes():
    """Lazy import all nodes to avoid circular imports and gRPC issues."""
    from core.ingestion.nodes.loader import LoaderNode
    from core.ingestion.nodes.router import RouterNode, route_file
    from core.ingestion.nodes.parser import CpuTextParser, GpuVisionParser
    from core.ingestion.nodes.chunker import SmartChunker
    from core.ingestion.nodes.embedder import BatchEmbedder
    from core.ingestion.nodes.indexer import DualIndexer
    from core.ingestion.nodes.quality_checker import QualityChecker
    from core.ingestion.nodes.error_handler import ErrorHandler
    from core.ingestion.nodes.finalizer import Finalizer
    
    return {
        'LoaderNode': LoaderNode,
        'RouterNode': RouterNode,
        'route_file': route_file,
        'CpuTextParser': CpuTextParser,
        'GpuVisionParser': GpuVisionParser,
        'SmartChunker': SmartChunker,
        'BatchEmbedder': BatchEmbedder,
        'DualIndexer': DualIndexer,
        'QualityChecker': QualityChecker,
        'ErrorHandler': ErrorHandler,
        'Finalizer': Finalizer,
    }


def _lazy_import_state_and_checkpoint():
    """Lazy import state and checkpoint to avoid database connection on import."""
    from core.state import IngestState
    from core.storage.checkpoint import get_postgres_saver
    return IngestState, get_postgres_saver


def _should_retry(state) -> str:
    """Decide whether to retry or proceed to finalizer after error handling."""
    if state.get("should_retry", False):
        retry_stage = state.get("processing_stage", "loader")
        if retry_stage in ["loader", "router", "cpu_parser", "gpu_parser"]:
            return "loader"  # Restart from loader
        return "chunker"  # Resume from chunker
    return "finalizer"


def _quality_gate(state) -> str:
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


def _check_indexer_error(state) -> str:
    """
    Check if indexer had errors and decide next step.
    
    P1-1 Fix: Route to error_handler if indexer errors occurred and retry is possible.
    
    Returns:
        "error_handler" if indexer errors exist and retry_count < 3
        "finalizer" otherwise
    """
    error_log = state.get("error_log", [])
    retry_count = state.get("retry_count", 0)
    
    # Check for indexer-specific errors
    indexer_errors = [e for e in error_log if e.get("stage") == "indexer"]
    
    if indexer_errors and retry_count < 3:
        return "error_handler"
    return "finalizer"


def create_ingest_graph():
    """
    Create the ingestion graph with full pipeline.
    
    Pipeline: 
    loader -> router -> cpu_parser/gpu_parser -> chunker -> qc -> embedder -> indexer -> finalizer
                                                              |
                                               error_handler <--> (retry or finalizer)
    
    P1 Fix: Uses lazy imports to avoid gRPC mutex lock on module import.
    """
    # Lazy import to avoid gRPC mutex lock
    StateGraph, END = _lazy_import_langgraph()
    IngestState, get_postgres_saver = _lazy_import_state_and_checkpoint()
    nodes = _lazy_import_nodes()
    
    workflow = StateGraph(IngestState)
    
    # Add Nodes
    workflow.add_node("loader", nodes['LoaderNode']())
    workflow.add_node("router", nodes['RouterNode']())
    workflow.add_node("cpu_parser", nodes['CpuTextParser']())
    workflow.add_node("gpu_parser", nodes['GpuVisionParser']())
    workflow.add_node("chunker", nodes['SmartChunker']())
    workflow.add_node("qc", nodes['QualityChecker']())  # P1 Fix: Quality checker
    workflow.add_node("embedder", nodes['BatchEmbedder']())
    workflow.add_node("indexer", nodes['DualIndexer']())
    workflow.add_node("error_handler", nodes['ErrorHandler']())  # P1 Fix: Error handler
    workflow.add_node("finalizer", nodes['Finalizer']())  # P1 Fix: Finalizer
    
    # Edges
    workflow.set_entry_point("loader")
    workflow.add_edge("loader", "router")
    
    # Conditional routing based on file type
    workflow.add_conditional_edges(
        "router",
        nodes['route_file'],
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
    
    # P1-1 Fix: Conditional edge from indexer to error_handler or finalizer
    workflow.add_conditional_edges(
        "indexer",
        _check_indexer_error,
        {
            "error_handler": "error_handler",
            "finalizer": "finalizer"
        }
    )
    
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


def create_ingest_graph_no_checkpoint():
    """
    Create the ingestion graph WITHOUT checkpointer.
    
    Useful for testing where checkpointing is not needed.
    
    Pipeline: 
    loader -> router -> cpu_parser/gpu_parser -> chunker -> qc -> embedder -> indexer -> finalizer
                                                              |
                                               error_handler <--> (retry or finalizer)
    """
    # Lazy import to avoid gRPC mutex lock
    StateGraph, END = _lazy_import_langgraph()
    IngestState, _ = _lazy_import_state_and_checkpoint()
    nodes = _lazy_import_nodes()
    
    workflow = StateGraph(IngestState)
    
    # Add Nodes
    workflow.add_node("loader", nodes['LoaderNode']())
    workflow.add_node("router", nodes['RouterNode']())
    workflow.add_node("cpu_parser", nodes['CpuTextParser']())
    workflow.add_node("gpu_parser", nodes['GpuVisionParser']())
    workflow.add_node("chunker", nodes['SmartChunker']())
    workflow.add_node("qc", nodes['QualityChecker']())
    workflow.add_node("embedder", nodes['BatchEmbedder']())
    workflow.add_node("indexer", nodes['DualIndexer']())
    workflow.add_node("error_handler", nodes['ErrorHandler']())
    workflow.add_node("finalizer", nodes['Finalizer']())
    
    # Edges
    workflow.set_entry_point("loader")
    workflow.add_edge("loader", "router")
    
    # Conditional routing based on file type
    workflow.add_conditional_edges(
        "router",
        nodes['route_file'],
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
    
    # Quality gate
    workflow.add_conditional_edges(
        "qc",
        _quality_gate,
        {
            "embedder": "embedder",
        }
    )
    
    # Main path
    workflow.add_edge("embedder", "indexer")
    
    # Conditional edge from indexer
    workflow.add_conditional_edges(
        "indexer",
        _check_indexer_error,
        {
            "error_handler": "error_handler",
            "finalizer": "finalizer"
        }
    )
    
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
    
    # Compile WITHOUT checkpointer
    app = workflow.compile()
    
    return app


# Legacy alias
def create_legacy_ingest_graph():
    """Alias for backward compatibility."""
    return create_ingest_graph()
