from typing import List, Optional, Dict, Any
import asyncio
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from .rag_state import RetrievedChunk
from .vector_store import VectorStore

class RetrievalService:
    """Hybrid retrieval service combining vector and keyword search"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=10000,
            stop_words='english',
            ngram_range=(1, 3),
            max_df=0.8,
            min_df=2
        )
    
    async def retrieve(
        self, 
        query: str, 
        top_k: int = 10,
        document_ids: Optional[List[str]] = None,
        hybrid_weight: float = 0.7,  # Weight for vector search vs keyword search
        rerank: bool = True
    ) -> List[RetrievedChunk]:
        """
        Perform hybrid retrieval combining vector and keyword search
        
        Args:
            query: User query
            top_k: Number of results to return
            document_ids: Optional filter for specific documents
            hybrid_weight: Weight for vector search (0.0 = pure keyword, 1.0 = pure vector)
            rerank: Whether to apply reranking
        
        Returns:
            List of retrieved chunks with scores
        """
        try:
            # Vector search
            vector_results = await self._vector_search(query, top_k * 2, document_ids)
            
            # Keyword search
            keyword_results = await self._keyword_search(query, top_k * 2, document_ids)
            
            # Combine results using hybrid approach
            combined_results = self._combine_results(
                vector_results, 
                keyword_results, 
                hybrid_weight
            )
            
            # Apply reranking if enabled
            if rerank:
                combined_results = await self._rerank_results(query, combined_results)
            
            # Return top_k results
            return combined_results[:top_k]
            
        except Exception as e:
            raise Exception(f"Retrieval failed: {str(e)}")
    
    async def _vector_search(
        self, 
        query: str, 
        top_k: int, 
        document_ids: Optional[List[str]] = None
    ) -> List[RetrievedChunk]:
        """Perform vector similarity search"""
        return await self.vector_store.search_similar_chunks(
            query=query,
            top_k=top_k,
            document_ids=document_ids,
            min_score=0.1
        )
    
    async def _keyword_search(
        self, 
        query: str, 
        top_k: int, 
        document_ids: Optional[List[str]] = None
    ) -> List[RetrievedChunk]:
        """Perform keyword-based search using TF-IDF"""
        try:
            # Get candidate chunks from vector store (broader search)
            candidate_chunks = await self.vector_store.search_similar_chunks(
                query=query,
                top_k=top_k * 3,  # Get more candidates for keyword filtering
                document_ids=document_ids,
                min_score=0.05  # Lower threshold for keyword candidates
            )
            
            if not candidate_chunks:
                return []
            
            # Prepare documents for TF-IDF
            documents = [chunk.content for chunk in candidate_chunks]
            
            # Fit TF-IDF vectorizer
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(documents)
            query_vector = self.tfidf_vectorizer.transform([query])
            
            # Calculate similarity scores
            similarities = cosine_similarity(query_vector, tfidf_matrix).flatten()
            
            # Create results with keyword scores
            keyword_results = []
            for i, (chunk, similarity) in enumerate(zip(candidate_chunks, similarities)):
                if similarity > 0.1:  # Minimum similarity threshold
                    chunk.score = float(similarity)  # Override with keyword score
                    keyword_results.append(chunk)
            
            # Sort by score and return top results
            keyword_results.sort(key=lambda x: x.score, reverse=True)
            return keyword_results[:top_k]
            
        except Exception as e:
            print(f"Keyword search failed: {e}")
            return []
    
    def _combine_results(
        self, 
        vector_results: List[RetrievedChunk], 
        keyword_results: List[RetrievedChunk],
        hybrid_weight: float
    ) -> List[RetrievedChunk]:
        """Combine vector and keyword search results"""
        
        # Create dictionaries for efficient lookup
        vector_dict = {chunk.id: chunk for chunk in vector_results}
        keyword_dict = {chunk.id: chunk for chunk in keyword_results}
        
        # Get all unique chunk IDs
        all_chunk_ids = set(vector_dict.keys()) | set(keyword_dict.keys())
        
        combined_results = []
        
        for chunk_id in all_chunk_ids:
            vector_chunk = vector_dict.get(chunk_id)
            keyword_chunk = keyword_dict.get(chunk_id)
            
            if vector_chunk and keyword_chunk:
                # Both results exist - combine scores
                combined_score = (
                    hybrid_weight * vector_chunk.score + 
                    (1 - hybrid_weight) * keyword_chunk.score
                )
                
                # Use the vector chunk as base (better metadata)
                combined_chunk = vector_chunk
                combined_chunk.score = combined_score
                combined_chunk.metadata["keyword_score"] = keyword_chunk.score
                combined_chunk.metadata["vector_score"] = vector_chunk.score
                
            elif vector_chunk:
                # Only vector result - use vector score with penalty
                combined_chunk = vector_chunk
                combined_chunk.score = vector_chunk.score * hybrid_weight
                
            elif keyword_chunk:
                # Only keyword result - use keyword score with penalty
                combined_chunk = keyword_chunk
                combined_chunk.score = keyword_chunk.score * (1 - hybrid_weight)
            
            combined_results.append(combined_chunk)
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x.score, reverse=True)
        return combined_results
    
    async def _rerank_results(
        self, 
        query: str, 
        results: List[RetrievedChunk]
    ) -> List[RetrievedChunk]:
        """Apply reranking to improve result quality"""
        try:
            # Simple reranking based on query-term overlap and position
            # This can be enhanced with more sophisticated models like BGE-Reranker
            
            query_terms = set(query.lower().split())
            
            for chunk in results:
                content_terms = set(chunk.content.lower().split())
                
                # Calculate term overlap
                overlap = len(query_terms & content_terms)
                overlap_score = overlap / len(query_terms) if query_terms else 0
                
                # Position bonus (earlier chunks get slight boost)
                position_bonus = max(0, 1.0 - (chunk.chunk_index * 0.01))
                
                # Update rerank score
                chunk.rerank_score = chunk.score * (1 + overlap_score * 0.2 + position_bonus * 0.1)
                chunk.metadata["rerank_score"] = chunk.rerank_score
                chunk.metadata["overlap_score"] = overlap_score
            
            # Sort by rerank score
            results.sort(key=lambda x: x.rerank_score or x.score, reverse=True)
            return results
            
        except Exception as e:
            print(f"Reranking failed: {e}")
            return results
    
    async def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get retrieval service statistics"""
        return {
            "service": "retrieval",
            "hybrid_weight": 0.7,
            "reranking_enabled": True,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "keyword_model": "TF-IDF"
        }