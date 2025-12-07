import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from elasticsearch import AsyncElasticsearch, Elasticsearch

from core.storage.config_store import load_storage_config

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

T = TypeVar("T")


class AsyncElasticsearchKeywordStore:
    def __init__(self):
        # Compatibility with server.config if possible + DB 配置
        cfg = load_storage_config()
        try:
            from server.config import settings

            url = getattr(settings, "elasticsearch_url", None)
        except Exception:
            url = None

        self.url = (
            cfg.get("keyword_url")
            or url
            or os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        )
        self.username = cfg.get("keyword_user") or os.environ.get("ELASTICSEARCH_USER")
        self.password = cfg.get("keyword_password") or os.environ.get("ELASTICSEARCH_PASSWORD")

        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)

        self._index_override = cfg.get("keyword_index")
        timeout = float(cfg.get("keyword_timeout") or 30)
        self.client = AsyncElasticsearch(
            self.url, basic_auth=auth, verify_certs=False, request_timeout=timeout
        )
        # Sync client for legacy support
        self.sync_client = Elasticsearch(
            self.url, basic_auth=auth, verify_certs=False, request_timeout=timeout
        )
        self.available = True

        if prometheus_client:
            self._metric_latency = prometheus_client.Histogram(
                "es_keyword_op_duration_ms",
                "ES keyword op latency (ms)",
                ["op", "index"],
                buckets=(5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000),
            )
            self._metric_errors = prometheus_client.Counter(
                "es_keyword_op_errors", "ES keyword op errors", ["op", "index"]
            )
        else:
            self._metric_latency = None
            self._metric_errors = None

    def _record(self, op: str, index: str, dur_ms: float, error: bool = False):
        if self._metric_latency:
            try:
                self._metric_latency.labels(op, index).observe(dur_ms)
            except Exception:
                pass
        if error and self._metric_errors:
            try:
                self._metric_errors.labels(op, index).inc()
            except Exception:
                pass

    def _with_retry(
        self, op: str, index: str, fn: Callable[[], T], attempts: int = 2, backoff_ms: int = 200
    ) -> T:
        last = None
        for i in range(attempts + 1):
            t0 = time.perf_counter()
            try:
                out = fn()
                self._record(op, index, (time.perf_counter() - t0) * 1000)
                return out
            except Exception as e:
                last = e
                self._record(op, index, (time.perf_counter() - t0) * 1000, error=True)
                if i >= attempts:
                    raise
                time.sleep(backoff_ms / 1000 * (2**i))
        raise last

    def try_init(self) -> bool:
        try:
            self.sync_client.info()
            return True
        except Exception:
            self.available = False
            return False

    async def ensure_index(self, index_name: str):
        async def _create():
            settings = {"analysis": {"analyzer": {"default": {"type": "smartcn"}}}}
            mappings = {
                "properties": {
                    "content": {"type": "text", "analyzer": "smartcn"},
                    "metadata": {"type": "object"},
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                }
            }
            try:
                await self.client.indices.create(
                    index=index_name, settings=settings, mappings=mappings
                )
            except Exception:
                settings["analysis"]["analyzer"]["default"]["type"] = "standard"
                mappings["properties"]["content"]["analyzer"] = "standard"
                if not await self.client.indices.exists(index=index_name):
                    await self.client.indices.create(
                        index=index_name, settings=settings, mappings=mappings
                    )

        exists = await self.client.indices.exists(index=index_name)
        if exists:
            return
        await _create()

    async def bulk_upsert(self, index_name: str, documents: list[dict[str, Any]]):
        from elasticsearch.helpers import async_bulk

        if not documents:
            return
        actions = []
        for doc in documents:
            doc_id = doc.get("id") or doc.get("chunk_id")
            action = {"_index": index_name, "_id": doc_id, "_source": doc}
            actions.append(action)

        async def _do():
            return await async_bulk(self.client, actions)

        t0 = time.perf_counter()
        try:
            await self._with_retry(
                "bulk_upsert", index_name, lambda: None, attempts=0
            )  # metric hook
            await _do()
            self._record("bulk_upsert", index_name, (time.perf_counter() - t0) * 1000)
        except Exception:
            self._record("bulk_upsert", index_name, (time.perf_counter() - t0) * 1000, error=True)
            raise

    async def search(
        self, index_name: str, query: str, limit: int = 10, filters: dict | None = None
    ) -> list[dict[str, Any]]:
        must = [{"match": {"content": query}}]
        filter_list = []

        if filters:
            for k, v in filters.items():
                filter_list.append({"term": {f"metadata.{k}": v}})

        body = {"query": {"bool": {"must": must, "filter": filter_list}}, "size": limit}
        try:
            t0 = time.perf_counter()
            resp = await self.client.search(index=index_name, body=body)
            dur = (time.perf_counter() - t0) * 1000
            self._record("search", index_name, dur)
            return [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "content": hit["_source"].get("content"),
                    "metadata": hit["_source"].get("metadata"),
                }
                for hit in resp["hits"]["hits"]
            ]
        except Exception:
            self._record("search", index_name, 0, error=True)
            return []

    # Legacy methods for compatibility
    def legacy_add(
        self, vec: Any, meta: dict[str, Any], index_name: str = "omnirag_chunks"
    ) -> None:
        """Sync add for backward compatibility"""
        # We ignore vector in ES legacy add usually unless it was dense_vector store
        doc = {
            "chunk_id": meta.get("id"),
            "document_id": meta.get("doc_id"),
            "content": meta.get("content"),
            "page_number": int(meta.get("page_num") or 0),
            "chunk_index": int(meta.get("chunk_index") or 0),
            "metadata": meta.get("metadata", {}),
        }
        self.sync_client.index(
            index=index_name, id=f"{meta.get('id')}-es", document=doc, refresh=True
        )

    def legacy_search(
        self, query: str, top_k: int = 5, index_name: str = "omnirag_chunks"
    ) -> list[tuple[dict[str, Any], float]]:
        body = {"size": top_k, "query": {"match": {"content": query}}}
        try:
            res = self.sync_client.search(index=index_name, body=body)
            hits = res.get("hits", {}).get("hits", [])
            out = []
            for h in hits:
                src = h.get("_source") or {}
                # Remap to legacy tuple format
                out.append((src, float(h.get("_score") or 0.0)))
            return out
        except Exception:
            return []


_KEYWORD_STORE: AsyncElasticsearchKeywordStore | None = None


def get_keyword_client() -> AsyncElasticsearchKeywordStore:
    global _KEYWORD_STORE
    if _KEYWORD_STORE is None:
        _KEYWORD_STORE = AsyncElasticsearchKeywordStore()
    return _KEYWORD_STORE
