import os
from uuid import uuid4
from fastapi import APIRouter, UploadFile, Depends
from fastapi.responses import FileResponse
from typing import List
from core.graph import create_graph
from server.schemas import UploadResponse, ChatRequest, ChatResponse, Source
from core.nodes.ingest import ingest
from core.storage.index_router import list_page_meta, doc_stats, delete_document
from core.model_gateway.config_store import load_config, save_config, validate_provider, provider_category
from server.auth import verify_token, create_token
import base64
import fitz

router = APIRouter()
secure_router = APIRouter(dependencies=[Depends(verify_token)])

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
    metas = list_page_meta(pdf_path, page_number)
    bboxes = []
    for m in metas:
        md = m.get("metadata", {})
        if md.get("type") == "table" and md.get("bbox"):
            x, y, w, h = md.get("bbox")
            bboxes.append({"x": x, "y": y, "w": w, "h": h})
    return {"image_base64": img_b64, "bboxes": bboxes}


@router.get("/documents/{document_id}/status")
async def get_document_status(document_id: str):
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    pdf_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    processing_status = "completed"
    processed_pages = 0
    total_pages = 0
    try:
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()
    except Exception:
        processing_status = "failed"
    stats = doc_stats(pdf_path)
    processed_pages = stats.get("processed_pages", 0)
    return {
        "document_id": document_id,
        "filename": os.path.basename(pdf_path),
        "processing_status": processing_status,
        "processed_pages": processed_pages,
        "total_pages": total_pages,
        "chunks_count": stats.get("chunk_count", 0),
    }


@router.delete("/documents/{document_id}")
async def delete_document_api(document_id: str):
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    pdf_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    removed = delete_document(pdf_path)
    file_removed = False
    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            file_removed = True
    except Exception:
        file_removed = False
    return {
        "document_id": document_id,
        "removed_chunks": removed,
        "file_removed": file_removed,
        "status": "ok"
    }


@router.get("/documents")
async def list_documents():
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    docs = []
    for fname in os.listdir(uploads_dir):
        if not fname.endswith(".pdf"):
            continue
        doc_id = fname.replace(".pdf", "")
        fpath = os.path.join(uploads_dir, fname)
        try:
            stat = os.stat(fpath)
            upload_date = stat.st_mtime
            file_size = stat.st_size
        except Exception:
            upload_date = 0
            file_size = 0
        status = await get_document_status(doc_id)
        docs.append({
            "id": doc_id,
            "filename": fname,
            "upload_date": upload_date,
            "processing_status": status.get("processing_status"),
            "processed_pages": status.get("processed_pages"),
            "total_pages": status.get("total_pages"),
            "file_size": file_size,
        })
    return {"documents": docs}


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    pdf_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    if not os.path.exists(pdf_path):
        return {"status": "error", "message": "not found"}
    return FileResponse(pdf_path, filename=f"{document_id}.pdf", media_type="application/pdf")


@secure_router.get("/models/providers")
async def get_providers():
    cfg = load_config()
    validations = [validate_provider(p.get("name")) for p in cfg.get("providers", [])]
    return {"config": cfg, "validations": validations}


@secure_router.post("/models/providers")
async def set_providers(payload: dict):
    cfg = load_config()
    if "providers" in payload:
        cfg["providers"] = payload["providers"]
    if "bindings" in payload:
        cfg["bindings"] = payload["bindings"]
    save_config(cfg)
    return {"status": "ok"}


@secure_router.post("/models/providers/test")
async def test_provider(payload: dict):
    name = payload.get("name")
    if not name:
        return {"status": "error", "message": "name required"}
    res = validate_provider(name)
    return {"status": "ok", "result": res}


@secure_router.get("/models/providers/groups")
async def get_providers_groups():
    cfg = load_config()
    groups = {"domestic": [], "foreign": [], "local": [], "other": []}
    vals = {}
    for p in cfg.get("providers", []):
        name = p.get("name")
        cat = provider_category(name)
        groups[cat].append(p)
        vals[name] = validate_provider(name)
    return {"groups": groups, "validations": vals}


@router.post("/auth/demo")
async def demo_login():
    token = create_token("demo-user")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    thread_id: str = req.conversation_id or str(uuid4())
    result = await rag_app.ainvoke({"query": req.query}, config={"configurable": {"thread_id": thread_id}})
    sources: List[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(Source(**{k: s.get(k) for k in ["chunk_id", "content", "score", "document_name", "page_number"]}))
    return ChatResponse(answer=result.get("answer", ""), sources=sources, conversation_id=thread_id, message_id=str(uuid4()))
