import asyncio
import os
from uuid import uuid4
from fastapi import APIRouter, UploadFile
from typing import List
from core.graph import create_graph
from api.schemas import UploadResponse, ChatRequest, ChatResponse, Source
from core.nodes.ingest import ingest
from core.storage.local_index import get_index
import base64
import fitz

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


@router.get("/documents/{document_id}/pages/{page_number}")
async def get_page_preview(document_id: str, page_number: int):
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    pdf_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    pix = page.get_pixmap(alpha=False, matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    doc.close()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    # collect bboxes
    idx = get_index()
    metas = idx.list_page_meta(pdf_path, page_number)
    bboxes = []
    for m in metas:
        md = m.get("metadata", {})
        if md.get("type") == "table" and md.get("bbox"):
            x, y, w, h = md.get("bbox")
            bboxes.append({"x": x, "y": y, "w": w, "h": h})
    return {"image_base64": img_b64, "bboxes": bboxes}

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = await rag_app.ainvoke({"query": req.query})
    sources: List[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(Source(**{k: s.get(k) for k in ["chunk_id", "content", "score", "document_name", "page_number"]}))
    return ChatResponse(answer=result.get("answer", ""), sources=sources, conversation_id=req.conversation_id, message_id=str(uuid4()))
