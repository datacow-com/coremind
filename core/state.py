from typing import Any, Dict, List, Optional, TypedDict

class ProcessedChunk(TypedDict):
    id: str
    content: str
    page_num: int
    doc_id: str
    chunk_index: int
    metadata: Dict[str, Any]

class RetrievedChunk(ProcessedChunk):
    score: float
    rerank_score: Optional[float]

class Source(TypedDict):
    chunk_id: Optional[str]
    content: Optional[str]
    score: Optional[float]
    document_name: Optional[str]
    page_number: Optional[int]

class RAGState(TypedDict, total=False):
    query: str
    documents: List[Dict[str, Any]]
    chunks: List[ProcessedChunk]
    vectors: List[List[float]]
    retrieved_chunks: List[RetrievedChunk]
    scores: List[float]
    context: str
    answer: str
    sources: List[Source]
    web_search_needed: bool
    hallucination_score: float
    step: str
    error: Optional[str]
    metadata: Dict[str, Any]
