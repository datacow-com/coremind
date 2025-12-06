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

def create_ingest_graph():
    workflow = StateGraph(IngestState)
    
    # Add Nodes
    workflow.add_node("loader", LoaderNode())
    workflow.add_node("router", RouterNode())
    workflow.add_node("cpu_parser", CpuTextParser())
    workflow.add_node("gpu_parser", GpuVisionParser())
    # Optional: Add Cleaner Node here if implemented
    workflow.add_node("chunker", SmartChunker())
    workflow.add_node("embedder", BatchEmbedder())
    workflow.add_node("indexer", DualIndexer())
    
    # Edges
    workflow.set_entry_point("loader")
    workflow.add_edge("loader", "router")
    
    workflow.add_conditional_edges(
        "router",
        route_file,
        {
            "cpu_parser": "cpu_parser",
            "gpu_parser": "gpu_parser"
        }
    )
    
    workflow.add_edge("cpu_parser", "chunker")
    workflow.add_edge("gpu_parser", "chunker")
    
    workflow.add_edge("chunker", "embedder")
    workflow.add_edge("embedder", "indexer")
    workflow.add_edge("indexer", END)
    
    # Compile with Checkpointer
    checkpointer = get_postgres_saver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app

