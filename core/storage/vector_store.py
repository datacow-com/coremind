import os
from typing import Any, List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, OptimizersConfigDiff, ScalarQuantization, ScalarQuantizationConfig, ScalarType

class QdrantVectorStore:
    def __init__(self):
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
            
        self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.environ.get("QDRANT_API_KEY")
        self.client = QdrantClient(url=self.url, api_key=self.api_key)
        self.available = True # Assume available if init succeeds, can refine with health check

    def try_init(self) -> bool:
        # Backward compatibility method
        try:
            self.client.get_collections()
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    async def ensure_collection(self, collection_name: str, dim: int = 1024, enable_quantization: bool = True):
        try:
            self.client.get_collection(collection_name)
        except Exception:
            quantization_config = None
            if enable_quantization:
                quantization_config = ScalarQuantization(
                    scalar=ScalarQuantizationConfig(
                        type=ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True
                    )
                )
            
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                optimizers_config=OptimizersConfigDiff(indexing_threshold=20000),
                quantization_config=quantization_config
            )

    async def upsert(self, collection_name: str, points: List[PointStruct], wait: bool = True):
        """Batch upsert points"""
        self.client.upsert(
            collection_name=collection_name,
            points=points,
            wait=wait
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
            wait=True
        )

    async def search(
        self, 
        collection_name: str, 
        query_vector: List[float], 
        limit: int = 10, 
        query_filter: Optional[Filter] = None
    ) -> List[Dict[str, Any]]:
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        return [
            {
                "id": point.id,
                "score": point.score,
                "content": point.payload.get("content"),
                "metadata": point.payload.get("metadata")
            }
            for point in results
        ]
        
    # Legacy search method compatibility
    def legacy_search(self, query_vec: Any, top_k: int = 5, collection_name: str = "omnirag_chunks") -> list[tuple[dict[str, Any], float]]:
        try:
            import numpy as np
            q = np.asarray(query_vec, dtype=np.float32).tolist()
        except Exception:
            q = list(query_vec)
            
        res = self.client.search(
            collection_name=collection_name,
            query_vector=q,
            limit=top_k,
            with_payload=True,
        )
        out: list[tuple[dict[str, Any], float]] = []
        for r in res:
            p = r.payload or {}
            # Map payload back to legacy format if needed
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
    
    async def scroll(self, collection_name: str, limit: int = 100, offset_id: Optional[str] = None) -> tuple[List[Dict[str, Any]], Optional[str]]:
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
            with_vectors=False # Usually don't need vectors for metadata processing
        )
        
        points = []
        for r in res:
            if isinstance(r, Record):
                points.append({
                    "id": r.id,
                    "content": r.payload.get("content"),
                    "metadata": r.payload.get("metadata"),
                    "doc_id": r.payload.get("doc_id")
                })
        return points, next_page_offset

_VECTOR_STORE: Optional[QdrantVectorStore] = None

def get_vector_client() -> QdrantVectorStore:
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = QdrantVectorStore()
    return _VECTOR_STORE
