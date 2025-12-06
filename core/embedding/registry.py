from typing import Optional
from core.embedding.provider_embedder import Embedder
from core.embedding.simple_embedder import embed_batch

class _SimpleEmbedderWrapper:
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str):
        # Return numpy array directly
        return embed_batch([text], self.dim)[0]

    def embed_batch(self, texts: list[str]):
        return embed_batch(texts, self.dim)

def get_embedder(dim: int = 256, provider: str | None = None, model_name: str | None = None):
    """
    Factory for obtaining an Embedder instance.
    
    Args:
        dim: Target dimension (deprecated, model determines dim)
        provider: 'simple' or 'auto' (default)
        model_name: Specific model ID (e.g. 'BAAI/bge-m3')
    """
    name = (provider or "auto").lower()
    if name == "simple":
        return _SimpleEmbedderWrapper(dim=dim)
    
    # Returns high-performance async embedder
    return Embedder(dim=dim, model_name=model_name)
