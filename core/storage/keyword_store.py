import os
from typing import Any, Dict, List, Optional
from elasticsearch import Elasticsearch, AsyncElasticsearch

class AsyncElasticsearchKeywordStore:
    def __init__(self):
        # Compatibility with server.config if possible
        try:
            from server.config import settings
            url = getattr(settings, "elasticsearch_url", None)
        except Exception:
            url = None
            
        self.url = url or os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
        self.username = os.environ.get("ELASTICSEARCH_USER")
        self.password = os.environ.get("ELASTICSEARCH_PASSWORD")
        
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
            
        self.client = AsyncElasticsearch(
            self.url, 
            basic_auth=auth, 
            verify_certs=False,
            request_timeout=30
        )
        # Sync client for legacy support
        self.sync_client = Elasticsearch(
            self.url,
            basic_auth=auth,
            verify_certs=False,
            request_timeout=30
        )
        self.available = True

    def try_init(self) -> bool:
        try:
            self.sync_client.info()
            return True
        except Exception:
            self.available = False
            return False

    async def ensure_index(self, index_name: str):
        if not await self.client.indices.exists(index=index_name):
            settings = {
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "smartcn"
                        }
                    }
                }
            }
            mappings = {
                "properties": {
                    "content": {"type": "text", "analyzer": "smartcn"},
                    "metadata": {"type": "object"},
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"}
                }
            }
            try:
                await self.client.indices.create(index=index_name, settings=settings, mappings=mappings)
            except Exception:
                settings["analysis"]["analyzer"]["default"]["type"] = "standard"
                mappings["properties"]["content"]["analyzer"] = "standard"
                if not await self.client.indices.exists(index=index_name):
                    await self.client.indices.create(index=index_name, settings=settings, mappings=mappings)

    async def bulk_upsert(self, index_name: str, documents: List[Dict[str, Any]]):
        from elasticsearch.helpers import async_bulk
        actions = []
        for doc in documents:
            doc_id = doc.get("id") or doc.get("chunk_id")
            action = {
                "_index": index_name,
                "_id": doc_id,
                "_source": doc
            }
            actions.append(action)
        
        await async_bulk(self.client, actions)

    async def search(self, index_name: str, query: str, limit: int = 10, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        must = [{"match": {"content": query}}]
        filter_list = []
        
        if filters:
            for k, v in filters.items():
                filter_list.append({"term": {f"metadata.{k}": v}})
        
        body = {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_list
                }
            },
            "size": limit
        }
        
        try:
            resp = await self.client.search(index=index_name, body=body)
            return [
                {
                    "id": hit["_id"],
                    "score": hit["_score"],
                    "content": hit["_source"].get("content"),
                    "metadata": hit["_source"].get("metadata")
                }
                for hit in resp["hits"]["hits"]
            ]
        except Exception:
            return []
            
    # Legacy methods for compatibility
    def legacy_add(self, vec: Any, meta: dict[str, Any], index_name: str = "omnirag_chunks") -> None:
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

    def legacy_search(self, query: str, top_k: int = 5, index_name: str = "omnirag_chunks") -> list[tuple[dict[str, Any], float]]:
        body = {
            "size": top_k,
            "query": {"match": {"content": query}}
        }
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

_KEYWORD_STORE: Optional[AsyncElasticsearchKeywordStore] = None

def get_keyword_client() -> AsyncElasticsearchKeywordStore:
    global _KEYWORD_STORE
    if _KEYWORD_STORE is None:
        _KEYWORD_STORE = AsyncElasticsearchKeywordStore()
    return _KEYWORD_STORE
