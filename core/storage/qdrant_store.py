import os
from typing import Any


class QdrantStore:
    def __init__(self, dim: int = 256, collection_name: str = "omnirag_chunks"):
        self.dim = dim
        self.collection_name = collection_name
        self.available = False
        self.client = None

    def try_init(self) -> bool:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams

            url = self._resolve_url()
            self.client = QdrantClient(url=url)
            exists = False
            try:
                info = self.client.get_collection(self.collection_name)
                exists = bool(info)
            except Exception:
                exists = False
            if not exists:
                self.client.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
                )
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def _resolve_url(self) -> str:
        try:
            from server.config import settings

            if getattr(settings, "qdrant_url", None):
                return str(settings.qdrant_url)
            host = getattr(settings, "qdrant_host", None)
            port = getattr(settings, "qdrant_port", None)
            if host and port:
                return f"http://{host}:{port}"
        except Exception:
            pass
        return os.environ.get("QDRANT_URL", "http://localhost:6333")

    def add(self, vec: Any, meta: dict[str, Any]) -> None:
        if not self.available or self.client is None:
            raise RuntimeError("QdrantStore not available")
        try:
            import numpy as np

            v = np.asarray(vec, dtype=np.float32).tolist()
        except Exception:
            v = list(vec)
        payload = {
            "id": meta.get("id"),
            "chunk_id": meta.get("id"),
            "document_id": meta.get("doc_id"),
            "content": meta.get("content"),
            "page_number": int(meta.get("page_num") or 0),
            "chunk_index": int(meta.get("chunk_index") or 0),
            "metadata": meta.get("metadata", {}),
        }
        self.client.upsert(
            collection_name=self.collection_name,
            points=[{"id": meta.get("id"), "vector": v, "payload": payload}],
        )

    def search(self, query_vec: Any, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self.available or self.client is None:
            return []
        try:
            import numpy as np

            q = np.asarray(query_vec, dtype=np.float32).tolist()
        except Exception:
            q = list(query_vec)
        res = self.client.search(
            collection_name=self.collection_name,
            query_vector=q,
            limit=top_k,
            with_payload=True,
        )
        out: list[tuple[dict[str, Any], float]] = []
        for r in res:
            p = r.payload or {}
            out.append(
                (
                    {
                        "id": p.get("chunk_id"),
                        "content": p.get("content"),
                        "page_num": p.get("page_number"),
                        "doc_id": p.get("document_id"),
                        "chunk_index": p.get("chunk_index"),
                        "metadata": p.get("metadata", {}),
                    },
                    float(r.score or 0.0),
                )
            )
        return out

    def delete_document(self, doc_id: str) -> int:
        if not self.available or self.client is None:
            return 0
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector={
                    "filter": {"must": [{"key": "document_id", "match": {"value": doc_id}}]}
                },
            )
            return 1
        except Exception:
            return 0
