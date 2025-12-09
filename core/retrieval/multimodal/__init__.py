"""
Multimodal Retrieval - Cross-modal search capabilities.

This package provides:
- ImageTextRetriever: Joint image-text retrieval
- MultimodalEmbedder: Unified embeddings for different modalities
- CrossModalSearch: Search across text, images, tables
"""

from core.retrieval.multimodal.embedder import (
    ModalityType,
    MultimodalEmbedder,
)
from core.retrieval.multimodal.retriever import (
    MultimodalResult,
    MultimodalRetriever,
)

__all__ = [
    "MultimodalRetriever",
    "MultimodalResult",
    "MultimodalEmbedder",
    "ModalityType",
]
