from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class DocumentChunk(BaseModel):
    id: str
    content: str
    page_number: int
    doc_id: str
    chunk_index: int
    metadata: Dict[str, Any] = {}

class RetrievedChunk(DocumentChunk):
    score: float
    rerank_score: Optional[float] = None

class Source(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_name: str
    page_number: int

class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    top_k: int = 5
    temperature: float = 0.7

class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    conversation_id: str
    message_id: str

class RAGState(BaseModel):
    # Input related
    query: str
    documents: List[str] = []
    
    # Processing process
    chunks: List[DocumentChunk] = []
    vectors: List[List[float]] = []
    
    # Retrieval results
    retrieved_chunks: List[RetrievedChunk] = []
    scores: List[float] = []
    
    # Generation results
    context: str = ""
    answer: str = ""
    sources: List[Source] = []
    
    # State management
    step: str = "ingestion"
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    # LangGraph specific fields
    web_search_needed: bool = False
    hallucination_score: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True