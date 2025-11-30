import os
from uuid import uuid4
from fastapi import APIRouter, UploadFile, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import Request
from typing import List
import json
from core.graph import create_graph
from server.schemas import UploadResponse, ChatRequest, ChatResponse, Source
from core.nodes.ingest import ingest
from core.storage.index_router import list_page_meta, doc_stats, delete_document, search as index_search, get_backends
from core.storage.local_index import get_index
from core.embedding.provider_embedder import Embedder
from core.nodes.retrieve import retrieve as retrieve_node
from core.nodes.rerank import rerank as rerank_node
from core.nodes.grade import grade as grade_node
from core.nodes.web_search import web_search as web_search_node
from core.state import RAGState
from core.llm.gateway import LLMGateway
from core.model_gateway.config_store import load_config, save_config, validate_provider, provider_category
from server.auth import verify_token, create_token
import base64
import time

router = APIRouter()
secure_router = APIRouter(dependencies=[Depends(verify_token)])

_rag_app = None

def get_rag_app():
    global _rag_app
    if _rag_app is None:
        _rag_app = create_graph()
    return _rag_app

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
    import fitz
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
    if "settings" in payload:
        s = payload["settings"]
        cfg["settings"] = {
            "vector_weight": float(s.get("vector_weight", cfg.get("settings", {}).get("vector_weight", 0.6))),
            "keyword_weight": float(s.get("keyword_weight", cfg.get("settings", {}).get("keyword_weight", 0.4))),
            "web_search_enabled": bool(s.get("web_search_enabled", cfg.get("settings", {}).get("web_search_enabled", True))),
        }
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
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    doc_paths = None
    if req.document_ids:
        doc_paths = [os.path.join(uploads_dir, f"{did}.pdf") for did in req.document_ids]
    state = {
        "query": req.query,
        "metadata": {
            "top_k": int(req.top_k or 5),
            "doc_paths": doc_paths,
        }
    }
    rag_app = get_rag_app()
    result = await rag_app.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    sources: List[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(Source(**{k: s.get(k) for k in ["chunk_id", "content", "score", "document_name", "page_number"]}))
    return ChatResponse(answer=result.get("answer", ""), sources=sources, conversation_id=thread_id, message_id=str(uuid4()))


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, request: Request):
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    doc_paths = None
    if req.document_ids:
        doc_paths = [os.path.join(uploads_dir, f"{did}.pdf") for did in req.document_ids]
    cfg = load_config()
    defaults = (cfg.get("settings") or {})
    meta = {
        "top_k": int(req.top_k or 5),
        "doc_paths": doc_paths,
        "vector_weight": float(req.vector_weight) if req.vector_weight is not None else float(defaults.get("vector_weight", 0.6)),
        "keyword_weight": float(req.keyword_weight) if req.keyword_weight is not None else float(defaults.get("keyword_weight", 0.4)),
        "web_search_enabled": True if req.web_search_enabled is None else bool(req.web_search_enabled),
    }

    state: RAGState = {"query": req.query, "metadata": meta}
    # phase: retrieve
    t_retrieve = time.perf_counter()
    ret = await retrieve_node(state)
    dur_retrieve = int((time.perf_counter() - t_retrieve) * 1000)
    chunks = ret.get("retrieved_chunks") or []
    context = "\n\n".join([c.get("content", "") for c in chunks])
    sources = []
    for c in chunks:
        sources.append({
            "chunk_id": c.get("id"),
            "content": c.get("content"),
            "score": c.get("score"),
            "document_name": c.get("doc_id"),
            "page_number": c.get("page_num"),
        })

    async def event_gen():
        nonlocal chunks, context
        rid = getattr(request.state, "request_id", None)
        yield "event: metadata\n" + "data: " + json.dumps({"request_id": rid}) + "\n\n"
        rag_app = get_rag_app()
        final_answer = None
        final_sources = []
        async for update in rag_app.astream({"query": req.query, "metadata": meta}, config={"configurable": {"thread_id": req.conversation_id or str(uuid4())}}):
            phase = update.get("step")
            if phase:
                payload = {"phase": phase, "status": "end"}
                metrics = update.get("metrics") or {}
                if metrics:
                    payload["metrics"] = metrics
                yield "event: thought\n" + "data: " + json.dumps(payload) + "\n\n"
            if update.get("retrieved_chunks"):
                chunks = update.get("retrieved_chunks") or []
                try:
                    for c in (chunks or [])[:meta.get("top_k", 5)]:
                        citation_payload = {
                            "doc_id": c.get("doc_id"),
                            "page": int(c.get("page_num") or 0),
                            "bbox": (c.get("metadata") or {}).get("bbox"),
                            "chunk_id": c.get("id"),
                            "score": float(c.get("rerank_score") or c.get("score") or 0.0),
                        }
                        yield "event: citation\n" + "data: " + json.dumps(citation_payload) + "\n\n"
                except Exception:
                    pass
            if update.get("context"):
                context = update.get("context") or context
            if update.get("sources"):
                final_sources = update.get("sources") or final_sources
            if update.get("answer"):
                final_answer = update.get("answer")
                yield "event: message\n" + "data: " + json.dumps({"delta": final_answer}) + "\n\n"
        final = {"sources": sources or final_sources, "conversation_id": req.conversation_id or str(uuid4()), "answer": final_answer}
        yield "event: message\n" + "data: " + json.dumps(final) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Connection": "close"})


@router.get("/vector-store/collections")
async def vector_collections():
    milvus, ok = get_backends()
    collections = []
    if ok and getattr(milvus, "collection", None) is not None:
        name = milvus.collection_name
        try:
            chunk_count = int(getattr(milvus.collection, "num_entities", 0))
        except Exception:
            chunk_count = 0
        collections.append({
            "name": name,
            "document_count": 0,
            "chunk_count": chunk_count,
            "embedding_dimension": milvus.dim,
            "distance_metric": "COSINE",
        })
    else:
        stats = get_index().stats_all()
        collections.append({
            "name": "local_index",
            "document_count": stats.get("document_count", 0),
            "chunk_count": stats.get("chunk_count", 0),
            "embedding_dimension": stats.get("embedding_dimension", 256),
            "distance_metric": "cosine",
        })
    return {"collections": collections}


@router.post("/vector-store/search")
async def vector_search(payload: dict):
    query = payload.get("query") or ""
    top_k = int(payload.get("top_k") or 10)
    emb = Embedder(dim=256)
    qvec = emb.embed(query)
    results = index_search(qvec, top_k=top_k) or []
    out = []
    for meta, score in results:
        out.append({
            "chunk_id": meta.get("id"),
            "content": meta.get("content"),
            "score": float(score),
            "document_name": meta.get("doc_id"),
            "page_number": int(meta.get("page_num") or 0),
        })
    return {"results": out}
