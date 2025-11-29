from typing import Dict, Any, List, Tuple
import numpy as np


class MilvusStore:
    def __init__(self, dim: int = 256, collection_name: str = "omnirag_chunks"):
        self.dim = dim
        self.collection_name = collection_name
        self.available = False
        self.collection = None

    def try_init(self) -> bool:
        try:
            from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
            import os
            uri = os.environ.get("MILVUS_URI") or "http://localhost:19530"
            connections.connect(alias="default", uri=uri)

            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
                FieldSchema(name="page_number", dtype=DataType.INT32),
                FieldSchema(name="chunk_index", dtype=DataType.INT32),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields, description="OmniRAG document chunks")

            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
            else:
                self.collection = Collection(name=self.collection_name, schema=schema)
                index_params = {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
                self.collection.create_index("embedding", index_params)

            self.collection.load()
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def add(self, vec: np.ndarray, meta: Dict[str, Any]) -> None:
        if not self.available:
            raise RuntimeError("MilvusStore not available")
        from pymilvus import MutationResult
        data = {
            "id": [f"{meta.get('id')}-milvus"],
            "chunk_id": [meta.get("id")],
            "document_id": [meta.get("doc_id")],
            "content": [meta.get("content")],
            "embedding": [vec.astype(np.float32).tolist()],
            "page_number": [int(meta.get("page_num") or 0)],
            "chunk_index": [int(meta.get("chunk_index") or 0)],
            "metadata": [meta.get("metadata", {})],
        }
        self.collection.insert(data)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not self.available:
            return []
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        results = self.collection.search(
            data=[query_vec.astype(np.float32).tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["chunk_id", "document_id", "content", "page_number", "chunk_index", "metadata"],
        )
        out: List[Tuple[Dict[str, Any], float]] = []
        for hits in results:
            for hit in hits:
                out.append(({
                    "id": hit.entity.get("chunk_id"),
                    "content": hit.entity.get("content"),
                    "page_num": hit.entity.get("page_number"),
                    "doc_id": hit.entity.get("document_id"),
                    "chunk_index": hit.entity.get("chunk_index"),
                    "metadata": hit.entity.get("metadata", {}),
                }, float(hit.score)))
        return out

    def delete_document(self, doc_id: str) -> int:
        if not self.available:
            return 0
        expr = f"document_id == '{doc_id}'"
        res = self.collection.delete(expr)
        try:
            # Some versions return MutationResult, we cannot get count reliably
            self.collection.flush()
        except Exception:
            pass
        return 1
