from typing import List, Optional, Dict, Any
import numpy as np
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, connections, utility
from sentence_transformers import SentenceTransformer
import uuid
import asyncio
from datetime import datetime

from .rag_state import DocumentChunk, RetrievedChunk
from .config import settings

class VectorStore:
    """Milvus-based vector store for document embeddings"""
    
    def __init__(self):
        self.collection = None
        self.embedding_model = None
        self.collection_name = settings.milvus_collection_name
        
    async def initialize(self):
        """Initialize Milvus connection and collection"""
        try:
            # Connect to Milvus
            connections.connect(
                alias="default",
                uri=settings.milvus_uri
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(settings.embedding_model)
            
            # Create or get collection
            await self._setup_collection()
            
        except Exception as e:
            raise Exception(f"Failed to initialize vector store: {str(e)}")
    
    async def _setup_collection(self):
        """Setup Milvus collection with proper schema"""
        # Define collection schema
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),  # all-MiniLM-L6-v2 dimension
            FieldSchema(name="page_number", dtype=DataType.INT32),
            FieldSchema(name="chunk_index", dtype=DataType.INT32),
            FieldSchema(name="score", dtype=DataType.FLOAT),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50)
        ]
        
        schema = CollectionSchema(fields, description="OmniRAG document chunks")
        
        # Create collection if it doesn't exist
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
        else:
            self.collection = Collection(name=self.collection_name, schema=schema)
            
            # Create index for vector field
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index("embedding", index_params)
        
        # Load collection into memory
        self.collection.load()
    
    async def add_document_chunks(self, document_id: str, chunks: List[DocumentChunk]) -> List[str]:
        """Add document chunks to vector store"""
        try:
            chunk_ids = []
            
            # Prepare data for insertion
            data = {
                "id": [],
                "chunk_id": [],
                "document_id": [],
                "content": [],
                "embedding": [],
                "page_number": [],
                "chunk_index": [],
                "score": [],
                "metadata": [],
                "created_at": []
            }
            
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                chunk_ids.append(chunk_id)
                
                # Generate embedding
                embedding = self.embedding_model.encode(chunk.content).tolist()
                
                data["id"].append(chunk_id)
                data["chunk_id"].append(chunk.id)
                data["document_id"].append(document_id)
                data["content"].append(chunk.content)
                data["embedding"].append(embedding)
                data["page_number"].append(chunk.page_number)
                data["chunk_index"].append(chunk.chunk_index)
                data["score"].append(0.0)  # Will be updated during retrieval
                data["metadata"].append(chunk.metadata)
                data["created_at"].append(datetime.utcnow().isoformat())
            
            # Insert data
            self.collection.insert(data)
            self.collection.flush()
            
            return chunk_ids
            
        except Exception as e:
            raise Exception(f"Failed to add chunks to vector store: {str(e)}")
    
    async def search_similar_chunks(
        self, 
        query: str, 
        top_k: int = 10,
        document_ids: Optional[List[str]] = None,
        min_score: float = 0.0
    ) -> List[RetrievedChunk]:
        """Search for similar chunks using vector similarity"""
        try:
            # Generate query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Build search parameters
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 16}
            }
            
            # Build filter if document_ids provided
            filter_expr = None
            if document_ids:
                doc_ids_str = "", "".join([f"'{doc_id}'" for doc_id in document_ids])
                filter_expr = f"document_id in [{doc_ids_str}]"
            
            # Perform vector search
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["chunk_id", "document_id", "content", "page_number", "chunk_index", "score", "metadata"]
            )
            
            # Convert results to RetrievedChunk objects
            retrieved_chunks = []
            for hits in results:
                for hit in hits:
                    if hit.score >= min_score:
                        chunk = RetrievedChunk(
                            id=hit.entity.get("chunk_id"),
                            content=hit.entity.get("content"),
                            page_number=hit.entity.get("page_number"),
                            doc_id=hit.entity.get("document_id"),
                            chunk_index=hit.entity.get("chunk_index"),
                            score=float(hit.score),
                            metadata=hit.entity.get("metadata", {})
                        )
                        retrieved_chunks.append(chunk)
            
            return retrieved_chunks
            
        except Exception as e:
            raise Exception(f"Vector search failed: {str(e)}")
    
    async def delete_document_chunks(self, document_id: str) -> bool:
        """Delete all chunks for a specific document"""
        try:
            # Delete by document_id
            delete_expr = f"document_id == '{document_id}'"
            self.collection.delete(delete_expr)
            self.collection.flush()
            return True
            
        except Exception as e:
            raise Exception(f"Failed to delete document chunks: {str(e)}")
    
    async def get_document_stats(self, document_id: str) -> Dict[str, Any]:
        """Get statistics for a document"""
        try:
            # Count chunks for document
            count_expr = f"document_id == '{document_id}'"
            count = self.collection.query(
                expr=count_expr,
                output_fields=["count(*)"]
            )
            
            return {
                "chunk_count": count[0]["count(*)"] if count else 0,
                "document_id": document_id
            }
            
        except Exception as e:
            raise Exception(f"Failed to get document stats: {str(e)}")
    
    async def close(self):
        """Close vector store connections"""
        try:
            if self.collection:
                self.collection.release()
            connections.disconnect("default")
        except Exception as e:
            print(f"Error closing vector store: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check vector store health"""
        try:
            # Check connection
            connections.get_connection_addr("default")
            
            # Check collection
            if self.collection:
                count = self.collection.num_entities
                return {
                    "status": "healthy",
                    "collection_name": self.collection_name,
                    "total_entities": count,
                    "embedding_model": settings.embedding_model
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": "Collection not initialized"
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }