import os
from typing import Any


class ElasticsearchStore:
    def __init__(self, dim: int = 256, index_name: str | None = None):
        self.dim = dim
        self.index_name = index_name or "omnirag_chunks"
        self.available = False
        self.client = None

    def try_init(self) -> bool:
        try:
            from elasticsearch import Elasticsearch
            from elasticsearch.exceptions import NotFoundError

            url = self._resolve_url()
            self.client = Elasticsearch(url, verify_certs=False)
            try:
                self.client.indices.get(index=self.index_name)
            except NotFoundError:
                body = {
                    "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
                    "mappings": {
                        "properties": {
                            "chunk_id": {"type": "keyword"},
                            "document_id": {"type": "keyword"},
                            "content": {"type": "text"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": self.dim,
                                "index": True,
                                "similarity": "cosine",
                            },
                            "page_number": {"type": "integer"},
                            "chunk_index": {"type": "integer"},
                            "metadata": {"type": "object", "enabled": True},
                        }
                    },
                }
                self.client.indices.create(index=self.index_name, body=body)
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def _resolve_url(self) -> str:
        try:
            from server.config import settings

            if getattr(settings, "elasticsearch_url", None):
                return str(settings.elasticsearch_url)
        except Exception:
            pass
        return os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")

    def add(self, vec: Any, meta: dict[str, Any]) -> None:
        if not self.available or self.client is None:
            raise RuntimeError("ElasticsearchStore not available")
        try:
            import numpy as np

            v = np.asarray(vec, dtype=np.float32).tolist()
        except Exception:
            v = list(vec)
        doc = {
            "chunk_id": meta.get("id"),
            "document_id": meta.get("doc_id"),
            "content": meta.get("content"),
            "embedding": v,
            "page_number": int(meta.get("page_num") or 0),
            "chunk_index": int(meta.get("chunk_index") or 0),
            "metadata": meta.get("metadata", {}),
        }
        self.client.index(
            index=self.index_name, id=f"{meta.get('id')}-es", document=doc, refresh=True
        )

    def search(self, query_vec: Any, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self.available or self.client is None:
            return []
        try:
            import numpy as np

            q = np.asarray(query_vec, dtype=np.float32).tolist()
        except Exception:
            q = list(query_vec)
        body = {
            "size": top_k,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.q, 'embedding') + 1.0",
                        "params": {"q": q},
                    },
                }
            },
            "_source": [
                "chunk_id",
                "document_id",
                "content",
                "page_number",
                "chunk_index",
                "metadata",
            ],
        }
        try:
            res = self.client.search(index=self.index_name, body=body)
            hits = res.get("hits", {}).get("hits", [])
            out: list[tuple[dict[str, Any], float]] = []
            for h in hits:
                s = float(h.get("_score") or 0.0)
                src = h.get("_source") or {}
                out.append(
                    (
                        {
                            "id": src.get("chunk_id"),
                            "content": src.get("content"),
                            "page_num": src.get("page_number"),
                            "doc_id": src.get("document_id"),
                            "chunk_index": src.get("chunk_index"),
                            "metadata": src.get("metadata", {}),
                        },
                        s,
                    )
                )
            return out
        except Exception:
            return []

    def delete_document(self, doc_id: str) -> int:
        if not self.available or self.client is None:
            return 0
        try:
            self.client.delete_by_query(
                index=self.index_name, body={"query": {"term": {"document_id": doc_id}}}
            )
            return 1
        except Exception:
            return 0
