"""
Ingestion nodes package.

This package contains all the processing nodes for the ingestion pipeline.
"""

# Import all node classes for easy access
from .chunker import SmartChunker
from .domain_router import DomainRouterNode
from .embedder import BatchEmbedder
from .error_handler import ErrorHandler
from .finalizer import Finalizer
from .indexer import DualIndexer
from .loader import LoaderNode
from .router import RouterNode

__all__ = [
    "SmartChunker",
    "DomainRouterNode",
    "BatchEmbedder", 
    "ErrorHandler",
    "Finalizer",
    "DualIndexer",
    "LoaderNode",
    "RouterNode",
]