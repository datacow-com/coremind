from typing import List, Optional
from pydantic import BaseModel

class Source(BaseModel):
    chunk_id: Optional[str] = None
    content: Optional[str] = None
    score: Optional[float] = None
    document_name: Optional[str] = None
    page_number: Optional[int] = None

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    estimated_time: Optional[int] = None

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    top_k: Optional[int] = 5
    temperature: Optional[float] = 0.7

class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
