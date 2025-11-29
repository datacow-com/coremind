import asyncio
from uuid import uuid4
from fastapi import APIRouter, UploadFile
from typing import List
from core.graph import create_graph
from api.schemas import UploadResponse, ChatRequest, ChatResponse, Source

router = APIRouter()

rag_app = create_graph()

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile):
    document_id = str(uuid4())
    return UploadResponse(document_id=document_id, filename=file.filename, status="processing", estimated_time=120)

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await rag_app.ainvoke({"query": req.query})
    sources: List[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(Source(**{k: s.get(k) for k in ["chunk_id", "content", "score", "document_name", "page_number"]}))
    return ChatResponse(answer=result.get("answer", ""), sources=sources, conversation_id=req.conversation_id, message_id=str(uuid4()))
