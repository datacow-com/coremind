import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    OptimizersConfigDiff,
    PointStruct,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

from core.storage.config_store import load_storage_config

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

T = TypeVar("T")


class QdrantVectorStore:
    def __init__(self):
        cfg = load_storage_config()
        # Try to load settings from existing config if available
        try:
            from server.config import settings

            url = getattr(settings, "qdrant_url", None)
            if not url:
                host = getattr(settings, "qdrant_host", None)
                port = getattr(settings, "qdrant_port", None)
                if host and port:
                    url = f"http://{host}:{port}"
        except Exception:
            url = None
        self.url = (
            cfg.get("vector_url") or url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        )
        self.api_key = cfg.get("vector_api_key") or os.environ.get("QDRANT_API_KEY")
        timeout = float(cfg.get("vector_timeout") or os.environ.get("QDRANT_TIMEOUT", "10"))
        self.client = QdrantClient(url=self.url, api_key=self.api_key, timeout=timeout)
        self.available = True  # Assume available if init succeeds, can refine with health check

        # metrics (optional)
        if prometheus_client:
            self._metric_latency = prometheus_client.Histogram(
                "qdrant_op_duration_ms",
                "Qdrant operation latency (ms)",
                ["op", "collection"],
                buckets=(5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000),
            )
            self._metric_errors = prometheus_client.Counter(
                "qdrant_op_errors", "Qdrant operation errors", ["op", "collection"]
            )
        else:
            self._metric_latency = None
            self._metric_errors = None

    def _record(self, op: str, collection: str | None, dur_ms: float, error: bool = False):
        if self._metric_latency:
            try:
                self._metric_latency.labels(op, collection or "").observe(dur_ms)
            except Exception:
                pass
        if error and self._metric_errors:
            try:
                self._metric_errors.labels(op, collection or "").inc()
            except Exception:
                pass

    def _with_retry(
        self,
        op: str,
        collection: str | None,
        fn: Callable[[], T],
        attempts: int = 2,
        backoff_ms: int = 200,
    ) -> T:
        last = None
        for i in range(attempts + 1):
            t0 = time.perf_counter()
            try:
                out = fn()
                self._record(op, collection, (time.perf_counter() - t0) * 1000)
                return out
            except Exception as e:  # pragma: no cover - best effort
                last = e
                self._record(op, collection, (time.perf_counter() - t0) * 1000, error=True)
                if i >= attempts:
                    raise
                time.sleep(backoff_ms / 1000 * (2**i))
        raise last

    def try_init(self) -> bool:
        # Backward compatibility method
        try:
            self.client.get_collections()
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    async def ensure_collection(
        self, collection_name: str, dim: int = 1024, enable_quantization: bool = True
    ):
        def _do():
            try:
                self.client.get_collection(collection_name)
                return
            except Exception:
                quantization_config = None
                if enable_quantization:
                    quantization_config = ScalarQuantization(
                        scalar=ScalarQuantizationConfig(
                            type=ScalarType.INT8, quantile=0.99, always_ram=True
                        )
                    )
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                    optimizers_config=OptimizersConfigDiff(indexing_threshold=20000),
                    quantization_config=quantization_config,
                )

        await asyncio.to_thread(self._with_retry, "ensure_collection", collection_name, _do)

    async def upsert(self, collection_name: str, points: list[PointStruct], wait: bool = True):
        """Batch upsert points with retry/metrics."""
        await asyncio.to_thread(
            self._with_retry,
            "upsert",
            collection_name,
            lambda: self.client.upsert(collection_name=collection_name, points=points, wait=wait),
        )

    # Legacy add method compatibility
    def add(self, vec: Any, meta: dict[str, Any]) -> None:
        """Legacy sync add method for backward compatibility with existing nodes"""
        import numpy as np

        try:
            v = np.asarray(vec, dtype=np.float32).tolist()
        except Exception:
            v = list(vec)

        # Infer collection name or use default
        collection_name = "omnirag_chunks"

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
            collection_name=collection_name,
            points=[PointStruct(id=meta.get("id"), vector=v, payload=payload)],
            wait=True,
        )

    async def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        query_filter: Filter | None = None,
    ) -> list[dict[str, Any]]:
        def _do():
            return self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )

        results = await asyncio.to_thread(self._with_retry, "search", collection_name, _do)
        return [
            {
                "id": point.id,
                "score": point.score,
                "content": point.payload.get("content"),
                "metadata": point.payload.get("metadata"),
            }
            for point in results
        ]

    # Legacy search method compatibility
    def legacy_search(
        self, query_vec: Any, top_k: int = 5, collection_name: str = "omnirag_chunks"
    ) -> list[tuple[dict[str, Any], float]]:
        try:
            import numpy as np

            q = np.asarray(query_vec, dtype=np.float32).tolist()
        except Exception:
            q = list(query_vec)
        res = self._with_retry(
            "legacy_search",
            collection_name,
            lambda: self.client.search(
                collection_name=collection_name,
                query_vector=q,
                limit=top_k,
                with_payload=True,
            ),
        )
        out: list[tuple[dict[str, Any], float]] = []
        for r in res:
            p = r.payload or {}
            out.append((p, float(r.score or 0.0)))
        return out

    async def delete(self, collection_name: str, points_selector: Any):
        self.client.delete(collection_name=collection_name, points_selector=points_selector)

    def delete_document(self, doc_id: str, collection_name: str = "omnirag_chunks") -> int:
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector={
                    "filter": {"must": [{"key": "document_id", "match": {"value": doc_id}}]}
                },
            )
            return 1
        except Exception:
            return 0

    # --- New Algorithm Support Methods ---

    async def scroll(
        self, collection_name: str, limit: int = 100, offset_id: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Scroll through collection for batch processing.
        Returns (points, next_offset_id)
        """
        from qdrant_client.models import Record

        res, next_page_offset = self.client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset_id,
            with_payload=True,
            with_vectors=False,  # Usually don't need vectors for metadata processing
        )

        points = []
        for r in res:
            if isinstance(r, Record):
                points.append(
                    {
                        "id": r.id,
                        "content": r.payload.get("content"),
                        "metadata": r.payload.get("metadata"),
                        "doc_id": r.payload.get("doc_id"),
                    }
                )
        return points, next_page_offset


_VECTOR_STORE: QdrantVectorStore | None = None


def get_vector_client() -> QdrantVectorStore:
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = QdrantVectorStore()
    return _VECTOR_STORE
