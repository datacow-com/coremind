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
    meta = {
        "top_k": int(req.top_k or 5),
        "doc_paths": doc_paths,
        "vector_weight": float(req.vector_weight) if req.vector_weight is not None else None,
        "keyword_weight": float(req.keyword_weight) if req.keyword_weight is not None else None,
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
        # meta
        rid = getattr(request.state, "request_id", None)
        yield "data: " + json.dumps({"type": "meta", "request_id": rid}) + "\n\n"
        # phases
        yield "data: " + json.dumps({"type": "phase", "name": "retrieve", "status": "end", "count": len(chunks), "duration_ms": dur_retrieve}) + "\n\n"
        # rerank
        t_rerank = time.perf_counter()
        try:
            rs = await rerank_node({"retrieved_chunks": chunks})
            chunks_reranked = rs.get("retrieved_chunks") or chunks
            yield "data: " + json.dumps({"type": "phase", "name": "rerank", "status": "end", "count": len(chunks_reranked), "duration_ms": int((time.perf_counter() - t_rerank) * 1000)}) + "\n\n"
            chunks = chunks_reranked
        except Exception:
            yield "data: " + json.dumps({"type": "phase", "name": "rerank", "status": "error"}) + "\n\n"
        # grade
        t_grade = time.perf_counter()
        web_needed = False
        try:
            gs = await grade_node({"retrieved_chunks": chunks, "metadata": meta})
            web_needed = bool(gs.get("web_search_needed"))
            yield "data: " + json.dumps({"type": "phase", "name": "grade", "status": "end", "web_search_needed": web_needed, "duration_ms": int((time.perf_counter() - t_grade) * 1000)}) + "\n\n"
        except Exception:
            yield "data: " + json.dumps({"type": "phase", "name": "grade", "status": "error"}) + "\n\n"
        # optional web_search
        if web_needed:
            t_ws = time.perf_counter()
            try:
                ws = await web_search_node({"query": req.query})
                extra_ctx = ws.get("context") or ""
                if extra_ctx:
                    nonlocal context
                    context = (context + "\n\n" + extra_ctx).strip()
                yield "data: " + json.dumps({"type": "phase", "name": "web_search", "status": "end", "duration_ms": int((time.perf_counter() - t_ws) * 1000)}) + "\n\n"
            except Exception:
                yield "data: " + json.dumps({"type": "phase", "name": "web_search", "status": "error"}) + "\n\n"
        # generate start
        gen_start = time.perf_counter()
        yield "data: " + json.dumps({"type": "phase", "name": "generate", "status": "start"}) + "\n\n"
        total_chars = 0
        total_words = 0
        gw = LLMGateway()
        async for delta in gw.stream_chat(prompt=req.query, context=context):
            try:
                payload = {"type": "answer", "delta": delta}
                yield "data: " + json.dumps(payload) + "\n\n"
                try:
                    total_chars += len(delta)
                    total_words += len(delta.split())
                except Exception:
                    pass
            except Exception:
                continue
        yield "data: " + json.dumps({"type": "phase", "name": "generate", "status": "end", "duration_ms": int((time.perf_counter() - gen_start) * 1000), "gen_chars": total_chars, "gen_words": total_words}) + "\n\n"
        final = {"type": "final", "sources": sources, "conversation_id": req.conversation_id or str(uuid4())}
        yield "data: " + json.dumps(final) + "\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


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
