from pydantic import BaseModel
from typing import Optional, List


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    estimated_time: int


class Source(BaseModel):
    chunk_id: Optional[str]
    content: Optional[str]
    score: Optional[float]
    document_name: Optional[str]
    page_number: Optional[int]


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    document_ids: Optional[List[str]] = None
    top_k: Optional[int] = 5
    temperature: Optional[float] = 0.7


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]
    conversation_id: Optional[str]
    message_id: Optional[str]
