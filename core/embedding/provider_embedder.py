from typing import List, Optional
import os
import numpy as np


def _normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec)) or 1.0
    return (vec / n).astype(np.float32)


def _reshape_to_dim(vec: np.ndarray, dim: int) -> np.ndarray:
    v = vec.astype(np.float32)
    if v.shape[-1] == dim:
        return _normalize(v)
    if v.shape[-1] > dim:
        return _normalize(v[:dim])
    pad = np.zeros(dim, dtype=np.float32)
    pad[: v.shape[-1]] = v
    return _normalize(pad)


class Embedder:
    def __init__(self, dim: int = 256, model_name: Optional[str] = None):
        self.dim = dim
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self._st = None
        self._openai_key = os.environ.get("OPENAI_API_KEY")
        if not self._openai_key:
            try:
                from sentence_transformers import SentenceTransformer
                self._st = SentenceTransformer(self.model_name)
            except Exception:
                self._st = None

    def embed(self, text: str) -> np.ndarray:
        if self._openai_key:
            try:
                import httpx
                with httpx.Client(timeout=15.0) as client:
                    r = client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={
                            "Authorization": f"Bearer {self._openai_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "text-embedding-3-small",
                            "input": text,
                        },
                    )
                    if r.status_code == 200:
                        data = r.json()["data"][0]["embedding"]
                        return _reshape_to_dim(np.array(data, dtype=np.float32), self.dim)
            except Exception:
                pass
        if self._st is not None:
            try:
                v = np.array(self._st.encode(text), dtype=np.float32)
                return _reshape_to_dim(v, self.dim)
            except Exception:
                pass
        from core.embedding.simple_embedder import embed as simple
        return simple(text, dim=self.dim)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return np.stack([self.embed(t) for t in texts], axis=0)

