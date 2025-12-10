"""
Embedder Registry - Factory for obtaining embedder instances.

Features:
- Embedder instance caching (P1 Fix #5)
- Multiple provider support
- Model-specific configuration
"""

from typing import Any

from core.embedding.provider_embedder import Embedder
from core.embedding.simple_embedder import embed_batch


class _SimpleEmbedderWrapper:
    """Simple embedder wrapper for basic use cases."""
    
    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str):
        # Return numpy array directly
        return embed_batch([text], self.dim)[0]

    def embed_batch(self, texts: list[str]):
        return embed_batch(texts, self.dim)


# P1 Fix #5: Embedder instance cache to avoid repeated DB queries
_EMBEDDER_CACHE: dict[str, Any] = {}


def get_embedder(
    dim: int = 256, 
    provider: str | None = None, 
    model_name: str | None = None,
    use_cache: bool = True,
) -> Any:
    """
    Factory for obtaining an Embedder instance.
    
    P1 Fix #5: Uses cached instances to avoid repeated DB queries and model loading.
    
    Args:
        dim: Target dimension (deprecated, model determines dim)
        provider: 'simple' or 'auto' (default)
        model_name: Specific model ID (e.g. 'BAAI/bge-m3')
        use_cache: Whether to use cached instance (default True)
        
    Returns:
        Embedder instance
    """
    name = (provider or "auto").lower()
    
    # Simple embedder - always create new (lightweight)
    if name == "simple":
        return _SimpleEmbedderWrapper(dim=dim)
    
    # Build cache key
    cache_key = f"{name}:{model_name or 'default'}:{dim}"
    
    # Check cache
    if use_cache and cache_key in _EMBEDDER_CACHE:
        return _EMBEDDER_CACHE[cache_key]
    
    # Create new embedder
    embedder = Embedder(dim=dim, model_name=model_name)
    
    # Cache it
    if use_cache:
        _EMBEDDER_CACHE[cache_key] = embedder
    
    return embedder


def clear_embedder_cache() -> None:
    """Clear the embedder cache. Useful for testing or config changes."""
    global _EMBEDDER_CACHE
    _EMBEDDER_CACHE.clear()


def get_cached_embedder_count() -> int:
    """Get number of cached embedders."""
    return len(_EMBEDDER_CACHE)
