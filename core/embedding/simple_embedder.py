import numpy as np


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t]


def embed(text: str, dim: int = 256) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    for tok in _tokenize(text):
        h = hash(tok) % dim
        vec[h] += 1.0
    # l2 normalize
    norm = np.linalg.norm(vec) or 1.0
    return vec / norm


def embed_batch(texts: list[str], dim: int = 256) -> np.ndarray:
    return np.stack([embed(t, dim=dim) for t in texts], axis=0)
