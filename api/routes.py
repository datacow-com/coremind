import asyncio
import os
from uuid import uuid4
from fastapi import APIRouter, UploadFile
from typing import List
from core.graph import create_graph
from api.schemas import UploadResponse, ChatRequest, ChatResponse, Source
from core.nodes.ingest import ingest

router = APIRouter()

rag_app = create_graph()

@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile):
    document_id = str(uuid4())
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    dest_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
    await ingest({"documents": [{"file_path": dest_path}]})
    return UploadResponse(document_id=document_id, filename=file.filename, status="completed", estimated_time=0)

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await rag_app.ainvoke({"query": req.query})
    sources: List[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(Source(**{k: s.get(k) for k in ["chunk_id", "content", "score", "document_name", "page_number"]}))
    return ChatResponse(answer=result.get("answer", ""), sources=sources, conversation_id=req.conversation_id, message_id=str(uuid4()))
