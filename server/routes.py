import asyncio
import base64
import importlib
import json
import os
import shlex
import subprocess
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

try:
    import prometheus_client
except Exception:  # pragma: no cover - optional dependency
    prometheus_client = None

from core.algorithms.graphrag_deep import create_graphrag_deep_graph
from core.algorithms.graphrag_light import create_graphrag_light_graph
from core.algorithms.mindmap_light import create_mindmap_light_graph
from core.algorithms.raptor_deep import create_raptor_deep_graph
from core.algorithms.raptor_light import create_raptor_light_graph
from core.graph import create_graph
from core.model_gateway.config_store import (
    load_config,
    provider_category,
    save_config,
    validate_provider,
)
from core.nodes.retrieve import retrieve as retrieve_node
from core.pipeline.kb_merge import merge_kb_params
from core.pipeline.rag_scenarios import get_rag_scenario_pipelines
from core.pipeline.registry import get_pipeline_registry
from core.state import RAGState
from core.storage.index_router import (
    delete_document,
    doc_stats,
    list_collections_info,
    list_page_meta,
)
from core.storage.kb_config import default_kb_config, load_kb_config, save_kb_config
from server.auth import get_current_user, verify_token
from server.chat_store import create_session, delete_session, list_sessions, update_session
from server.config import settings
from server.schemas import ChatRequest, ChatResponse, Source, UploadResponse

LLMGateway = importlib.import_module("core.llm.gateway").LLMGateway

# router：业务接口默认受保护
router = APIRouter(dependencies=[Depends(verify_token)])
# secure_router：兼容已存在的受保护路由
secure_router = APIRouter(dependencies=[Depends(verify_token)])

_rag_app = None
_SSE_SEM: asyncio.Semaphore | None = (
    asyncio.Semaphore(int(getattr(settings, "sse_max_connections", 0) or 0))
    if int(getattr(settings, "sse_max_connections", 0) or 0) > 0
    else None
)
_METRICS: dict[str, int] = {
    "uploads_ok": 0,
    "uploads_reject": 0,
    "uploads_scan_fail": 0,
    "sse_active": 0,
}
if prometheus_client:
    _PROM_UPLOAD_OK = prometheus_client.Counter("uploads_ok", "Successful uploads")
    _PROM_UPLOAD_REJECT = prometheus_client.Counter("uploads_reject", "Rejected uploads")
    _PROM_UPLOAD_SCAN_FAIL = prometheus_client.Counter(
        "uploads_scan_fail", "Uploads rejected by scanner"
    )
    _PROM_SSE_ACTIVE = prometheus_client.Gauge("sse_active", "Active SSE connections")
else:  # pragma: no cover
    _PROM_UPLOAD_OK = _PROM_UPLOAD_REJECT = _PROM_UPLOAD_SCAN_FAIL = _PROM_SSE_ACTIVE = None


def get_rag_app():
    global _rag_app
    if _rag_app is None:
        _rag_app = create_graph()
    return _rag_app


def _kb_registry_add(kb_name: str, entry: dict[str, Any]) -> None:
    try:
        from core.storage.kb_config_db import register_doc
        register_doc(kb_name, entry)
    except Exception:
        pass


def _kb_registry_remove(document_id: str, kb_name: str | None = None) -> None:
    try:
        from core.storage.kb_config_db import remove_doc
        remove_doc(document_id, kb_name)
    except Exception:
        pass


def _sniff_mime(content: bytes) -> str:
    """
    轻量文件头检测：覆盖常见类型，用于与 content_type 交叉校验。
    """
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if content.startswith(b"PK\x03\x04"):
        return "application/zip"
    return ""


def _scan_file(path: str) -> None:
    """
    可选病毒扫描钩子：设置 UPLOAD_SCAN_CMD 启用（如 'clamscan --no-summary'）。
    未配置则跳过，扫描失败或命中直接拒绝。
    """
    cmd = os.environ.get("UPLOAD_SCAN_CMD")
    if not cmd:
        return
    try:
        parts = shlex.split(cmd) + [path]
        res = subprocess.run(parts, capture_output=True, timeout=15)
        if res.returncode != 0:
            raise HTTPException(status_code=400, detail="file rejected by scanner")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="file scan failed")


def _validate_upload(file: UploadFile, content: bytes) -> None:
    """
    额外的结构校验：
    - 非空文件
    - 仅允许 .pdf 扩展（现有接口约定），且魔数必须是 PDF
    - MIME 与白名单交叉验证
    """
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    max_bytes = int(getattr(settings, "upload_max_bytes", 20 * 1024 * 1024))
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="file too large")
    sniff = _sniff_mime(content)
    allowed = set(getattr(settings, "upload_allowed_mime_types", []))
    ctype = (file.content_type or "").lower()

    def _reject():
        raise HTTPException(status_code=415, detail="unsupported media type")

    def _require_pdf_checks():
        max_pages = int(getattr(settings, "upload_max_pages", 200) or 200)
        max_pixels = int(getattr(settings, "upload_max_page_pixels", 50_000_000) or 50_000_000)
        try:
            import fitz
        except Exception as err:  # pragma: no cover
            raise HTTPException(
                status_code=500, detail=f"pdf validator unavailable: {err}"
            ) from err
        try:
            doc = fitz.open(stream=content, filetype="pdf")
        except Exception:
            raise HTTPException(status_code=415, detail="invalid pdf")
        try:
            if doc.is_encrypted or getattr(doc, "needs_pass", False):
                raise HTTPException(status_code=415, detail="encrypted pdf not allowed")
            if doc.page_count > max_pages:
                raise HTTPException(status_code=413, detail="too many pages")
            try:
                emb = list(getattr(doc, "embeddedFileNames", []) or [])
                if emb:
                    raise HTTPException(status_code=415, detail="embedded files not allowed")
            except Exception:
                pass
            for i in range(min(doc.page_count, max_pages)):
                p = doc.load_page(i)
                w, h = p.rect.width, p.rect.height
                if (w * h) > max_pixels:
                    raise HTTPException(status_code=413, detail="page too large")
        finally:
            try:
                doc.close()
            except Exception:
                pass

    # MIME/魔数与扩展名交叉校验
    if allowed:
        if (sniff and sniff not in allowed) and (ctype not in allowed):
            _reject()
        if not sniff and (ctype not in allowed):
            _reject()

    # 按扩展/魔数分类验证
    if ext in {".pdf"}:
        if sniff and sniff != "application/pdf":
            _reject()
        _require_pdf_checks()
        return
    # OOXML
    if ext in {".docx", ".pptx", ".xlsx"}:
        if not sniff or sniff != "application/zip":
            _reject()
        return
    # HTML
    if ext == ".html":
        if sniff and sniff not in {"text/html", "application/zip", "application/xml"}:
            _reject()
        return
    # EML
    if ext == ".eml":
        if sniff and sniff not in {"message/rfc822", ""}:
            _reject()
        # Simple header check
        header = content[:200].decode(errors="ignore").lower()
        if "subject:" not in header and "from:" not in header:
            _reject()
        return
    # Images (already covered by sniff)
    if ext in {".png", ".jpg", ".jpeg"}:
        if sniff not in {"image/png", "image/jpeg"}:
            _reject()
        # optional dimension check (Pillow best-effort)
        max_pixels_img = int(getattr(settings, "image_max_pixels", 50_000_000) or 50_000_000)
        try:
            from io import BytesIO

            from PIL import Image  # type: ignore

            img = Image.open(BytesIO(content))
            w, h = img.size
            if (w * h) > max_pixels_img:
                raise HTTPException(status_code=413, detail="image too large")
        except HTTPException:
            raise
        except Exception:
            # 如果无法解析，不阻断（已有体积/扫描保护）
            pass
        return
    # Markdown / text
    if ext == ".md":
        max_md_bytes = int(getattr(settings, "markdown_max_bytes", 2 * 1024 * 1024))
        max_md_lines = int(getattr(settings, "markdown_max_lines", 5000))
        if len(content) > max_md_bytes:
            raise HTTPException(status_code=413, detail="markdown too large")
        try:
            txt = content.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(status_code=415, detail="invalid markdown encoding")
        if txt.count("\n") > max_md_lines:
            raise HTTPException(status_code=413, detail="too many lines in markdown")
        return
    _reject()


def _should_index(kb_name: str | None, ext: str, requested: bool) -> bool:
    if requested:
        return True
    if not kb_name:
        return False
    try:
        kbc = load_kb_config(str(kb_name))
        sel = (kbc.get("ingestion_pipeline") or {}).get("selected_pipeline") or ""
        if ext == ".pdf" and sel == "pdf_index":
            return True
        if ext == ".md" and sel == "markdown_index":
            return True
    except Exception:
        pass
    return False


@secure_router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile,
    kb_name: str | None = None,
    index: bool = False,
    user: dict[str, Any] = Depends(get_current_user),
):
    return UploadResponse(
        document_id="",
        filename=str(file.filename or "document.pdf"),
        status="error",
        estimated_time=0,
    )


@router.get("/documents/{document_id}/pages/{page_number}")
async def get_page_preview(document_id: str, page_number: int):
    uploads_dir = settings.uploads_dir_resolved
    pdf_path = os.path.join(uploads_dir, f"{document_id}.pdf")
    import asyncio

    import fitz

    def _render() -> bytes:
        d = fitz.open(pdf_path)
        try:
            p = d.load_page(page_number - 1)
            px = p.get_pixmap(alpha=False, matrix=fitz.Matrix(2, 2))
            return px.tobytes("png")
        finally:
            d.close()

    img_bytes = await asyncio.to_thread(_render)
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
    return {"status": "error", "message": "deprecated, use /api/ingest/upload_run/stream for progress"}


@router.delete("/documents/{document_id}")
async def delete_document_api(document_id: str):
    removed = delete_document(document_id)
    _kb_registry_remove(document_id)
    return {"document_id": document_id, "removed_chunks": removed, "status": "ok"}


@router.get("/documents")
async def list_documents():
    return {"status": "error", "message": "deprecated, use /api/ingest/upload_run"}


@router.get("/documents/{document_id}/download")
async def download_document(document_id: str):
    return {"status": "error", "message": "deprecated, use /api/ingest/upload_run with blob storage"}


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
            "vector_weight": float(
                s.get("vector_weight", cfg.get("settings", {}).get("vector_weight", 0.6))
            ),
            "keyword_weight": float(
                s.get("keyword_weight", cfg.get("settings", {}).get("keyword_weight", 0.4))
            ),
            "web_search_enabled": bool(
                s.get("web_search_enabled", cfg.get("settings", {}).get("web_search_enabled", True))
            ),
        }
    save_config(cfg)
    return {"status": "ok"}


@secure_router.post("/models/providers/test")
async def provider_test_route(payload: dict | None = None):
    payload = payload or {}
    name = payload.get("name")
    if not name:
        return {"status": "error", "message": "name required"}
    res = validate_provider(name)
    return {"status": "ok", "result": res}


try:
    provider_test_route.__test__ = False
except Exception:
    pass


class _ProviderCaller:
    async def __call__(self, payload: dict | None = None):
        return await provider_test_route(payload)


# exported alias without test_ prefix to avoid pytest collection warnings
provider_test = _ProviderCaller()
try:
    provider_test.__test__ = False
except Exception:
    pass


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


@secure_router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: dict[str, Any] = Depends(get_current_user)):
    thread_id: str = req.conversation_id or str(uuid4())
    uploads_dir = settings.uploads_dir_resolved
    doc_paths = None
    if req.document_ids:
        doc_paths = [os.path.join(uploads_dir, f"{did}.pdf") for did in req.document_ids]
    # Build metadata with KB overlay
    vw = float(getattr(settings, "vector_weight", 0.6))
    kw = float(getattr(settings, "keyword_weight", 0.4))
    tk = int(req.top_k or settings.top_k_default)
    ck = int(req.candidate_k or getattr(settings, "candidate_k", 50))
    meta_base = {
        "top_k": tk,
        "candidate_k": ck,
        "doc_paths": doc_paths,
        "lang_hint": (req.lang_hint or None),
        "kb_name": (req.kb_name or None),
        "vector_weight": vw,
        "keyword_weight": kw,
        "reranker_filter_threshold": float(getattr(settings, "reranker_filter_threshold", 0.2)),
        "grade_threshold": float(getattr(settings, "grade_threshold", 0.5)),
        "hallucination_threshold": float(getattr(settings, "hallucination_threshold", 0.5)),
    }
    if req.kb_name:
        try:
            kbc = load_kb_config(req.kb_name)
            meta_base.update(
                {
                    "top_k": int(kbc.get("top_k_default", tk) or tk),
                    "candidate_k": int(kbc.get("candidate_k", ck) or ck),
                    "vector_weight": float(kbc.get("vector_weight", vw) or vw),
                    "keyword_weight": float(kbc.get("keyword_weight", kw) or kw),
                    "reranker_filter_threshold": float(
                        kbc.get("reranker_filter_threshold", meta_base["reranker_filter_threshold"])
                    )
                    if kbc.get("reranker_filter_threshold") is not None
                    else meta_base["reranker_filter_threshold"],
                    "grade_threshold": float(
                        kbc.get("grade_threshold", meta_base["grade_threshold"])
                    )
                    if kbc.get("grade_threshold") is not None
                    else meta_base["grade_threshold"],
                    "hallucination_threshold": float(
                        kbc.get("hallucination_threshold", meta_base["hallucination_threshold"])
                    )
                    if kbc.get("hallucination_threshold") is not None
                    else meta_base["hallucination_threshold"],
                }
            )
        except Exception:
            pass
    state = {
        "query": req.query,
        "metadata": meta_base,
    }
    rag_app = get_rag_app()
    result = await rag_app.ainvoke(state, config={"configurable": {"thread_id": thread_id}})
    sources: list[Source] = []
    raw_sources = result.get("sources") or []
    for s in raw_sources:
        sources.append(
            Source(
                **{
                    k: s.get(k)
                    for k in ["chunk_id", "content", "score", "document_name", "page_number"]
                }
            )
        )
    return ChatResponse(
        answer=result.get("answer", ""),
        sources=sources,
        conversation_id=thread_id,
        message_id=str(uuid4()),
    )


@secure_router.get("/chat/sessions")
async def chat_sessions(user: dict[str, Any] = Depends(get_current_user)):
    sessions = await list_sessions()
    return {"code": 0, "message": "ok", "data": {"sessions": sessions}}


@secure_router.post("/chat/sessions")
async def chat_sessions_create(
    payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)
):
    item = await create_session(payload or {})
    return {"code": 0, "message": "ok", "data": {"session": item}}


@secure_router.patch("/chat/sessions/{sid}")
async def chat_sessions_update(
    sid: str, payload: dict[str, Any], user: dict[str, Any] = Depends(get_current_user)
):
    item = await update_session(sid, payload or {})
    if not item:
        return JSONResponse(status_code=404, content={"code": 404, "message": "session_not_found"})
    return {"code": 0, "message": "ok", "data": {"session": item}}


@secure_router.delete("/chat/sessions/{sid}")
async def chat_sessions_delete(sid: str, user: dict[str, Any] = Depends(get_current_user)):
    ok = await delete_session(sid)
    if not ok:
        return JSONResponse(status_code=404, content={"code": 404, "message": "session_not_found"})
    return {"code": 0, "message": "ok"}


@secure_router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest, request: Request, user: dict[str, Any] = Depends(get_current_user)
):
    # Check if we should use new V4 QA Graph
    use_new_pipeline = False
    if req.kb_name:
        try:
            kbc = load_kb_config(req.kb_name)
            use_new_pipeline = kbc.get("use_new_pipeline", True)
        except:
            pass

    if use_new_pipeline:
        # Redirect to new QA Graph
        from core.retrieval.graph import create_qa_graph
        from core.state import RetrievalState

        initial_state = RetrievalState(
            query_id=str(uuid4()),
            input_query=req.query,
            chat_history=[],
            kb_name=req.kb_name or "default",
            user_id=user.get("id", "anonymous"),
            strategy_config={
                "top_k": req.top_k,
                "embedding_model": getattr(settings, "embedding_model", "BAAI/bge-m3")
            },
            preprocessed_queries=[],
            intent={},
            vector_results=[],
            keyword_results=[],
            fused_results=[],
            reranked_results=[],
            retrieved_chunks=[],
            relevance_score=0.0,
            is_relevant=True,
            loop_count=0,
            answer="",
            final_answer="",
            citations=[],
            confidence=0.0,
            sources=[]
        )

        app = create_qa_graph()

        async def event_gen():
            yield "data: " + json.dumps({"type": "meta", "request_id": str(uuid4())}) + "\n\n"
            async for event in app.astream_events(initial_state, version="v1"):
                event_type = event['event']
                if event_type == "on_chain_start":
                    yield "data: " + json.dumps({"type": "phase", "name": event['name'], "status": "start"}) + "\n\n"
                elif event_type == "on_chain_end":
                    if event['name'] == 'generator':
                        output = event['data'].get('output', {})
                        final_answer = output.get('final_answer', "")
                        citations = output.get('citations', [])
                        for c in citations:
                            cit_payload = {
                                "doc_id": c.get("doc_id"),
                                "page": c.get("page"),
                                "bbox": c.get("bbox"),
                                "chunk_id": c.get("chunk_id"),
                                "score": 1.0,
                                "content": c.get("content")
                            }
                            yield "data: " + json.dumps({"type": "citation", **cit_payload}) + "\n\n"
                        yield "data: " + json.dumps({"type": "answer", "delta": final_answer}) + "\n\n"
                        final_payload = {
                            "type": "final",
                            "answer": final_answer,
                            "sources": citations,
                            "conversation_id": req.conversation_id or str(uuid4())
                        }
                        yield "data: " + json.dumps(final_payload) + "\n\n"
                    yield "data: " + json.dumps({"type": "phase", "name": event['name'], "status": "end"}) + "\n\n"

        return StreamingResponse(
            event_gen(), media_type="text/event-stream", headers={"Connection": "close"}
        )

    sem_acquired = False
    if _SSE_SEM:
        try:
            await asyncio.wait_for(_SSE_SEM.acquire(), timeout=1.0)
            sem_acquired = True
            if _PROM_SSE_ACTIVE:
                _PROM_SSE_ACTIVE.inc()
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"error": "too_many_streams", "message": "SSE connection limit reached"},
            )
    uploads_dir = settings.uploads_dir_resolved
    doc_paths = None
    if req.document_ids:
        doc_paths = [os.path.join(uploads_dir, f"{did}.pdf") for did in req.document_ids]
    meta = {
        "top_k": int(req.top_k or 5),
        "candidate_k": int(req.candidate_k or getattr(settings, "candidate_k", 50)),
        "doc_paths": doc_paths,
        "vector_weight": float(req.vector_weight)
        if req.vector_weight is not None
        else float(getattr(settings, "vector_weight", 0.6)),
        "keyword_weight": float(req.keyword_weight)
        if req.keyword_weight is not None
        else float(getattr(settings, "keyword_weight", 0.4)),
        "web_search_enabled": bool(req.web_search_enabled)
        if req.web_search_enabled is not None
        else bool(getattr(settings, "web_search_enabled", True)),
        "reranker_filter_threshold": float(req.reranker_threshold)
        if req.reranker_threshold is not None
        else float(getattr(settings, "reranker_filter_threshold", 0.2)),
        "lang_hint": (req.lang_hint or None),
        "kb_name": (req.kb_name or None),
    }
    if req.kb_name:
        try:
            kbc = load_kb_config(req.kb_name)
            meta.update(
                {
                    "top_k": int(kbc.get("top_k_default", meta["top_k"]))
                    if kbc.get("top_k_default") is not None
                    else meta["top_k"],
                    "candidate_k": int(kbc.get("candidate_k", meta["candidate_k"]))
                    if kbc.get("candidate_k") is not None
                    else meta["candidate_k"],
                    "vector_weight": float(kbc.get("vector_weight", meta["vector_weight"]))
                    if kbc.get("vector_weight") is not None
                    else meta["vector_weight"],
                    "keyword_weight": float(kbc.get("keyword_weight", meta["keyword_weight"]))
                    if kbc.get("keyword_weight") is not None
                    else meta["keyword_weight"],
                    "reranker_filter_threshold": float(
                        kbc.get("reranker_filter_threshold", meta["reranker_filter_threshold"])
                    )
                    if kbc.get("reranker_filter_threshold") is not None
                    else meta["reranker_filter_threshold"],
                    "grade_threshold": float(
                        kbc.get("grade_threshold", getattr(settings, "grade_threshold", 0.5))
                    ),
                    "hallucination_threshold": float(
                        kbc.get(
                            "hallucination_threshold",
                            getattr(settings, "hallucination_threshold", 0.5),
                        )
                    ),
                }
            )
        except Exception:
            pass

    state: RAGState = {"query": req.query, "metadata": meta}
    # phase: retrieve
    ret = await retrieve_node(state)
    chunks = ret.get("retrieved_chunks") or []
    context = "\n\n".join([c.get("content", "") for c in chunks])
    sources = []
    for c in chunks:
        sources.append(
            {
                "chunk_id": c.get("id"),
                "content": c.get("content"),
                "score": c.get("score"),
                "document_name": c.get("doc_id"),
                "page_number": c.get("page_num"),
            }
        )

    async def event_gen():
        nonlocal chunks, context
        rid = getattr(request.state, "request_id", None)
        start_ts = time.time()
        try:
            if _SSE_SEM:
                _METRICS["sse_active"] += 1
            yield "data: " + json.dumps({"type": "meta", "request_id": rid}) + "\n\n"
            ts = int(time.time() * 1000)
            yield "event: ping\n" + "data: " + json.dumps({"type": "ping", "ts": ts}) + "\n\n"
            yield (
                "data: "
                + json.dumps(
                    {"type": "phase", "name": "retrieve", "status": "end", "count": len(chunks)}
                )
                + "\n\n"
            )
            rag_app = get_rag_app()
            final_answer = None
            final_sources = []
            interval = int(getattr(settings, "sse_heartbeat_interval", 0) or 0)
            last_ping = time.time()
            timeout_s = int(getattr(settings, "sse_client_timeout", 0) or 0)
            async for update in rag_app.astream(
                {"query": req.query, "metadata": meta},
                config={"configurable": {"thread_id": req.conversation_id or str(uuid4())}},
            ):
                if timeout_s and (time.time() - start_ts) > timeout_s:
                    yield "event: close\n" + "data: " + json.dumps({"type": "timeout"}) + "\n\n"
                    break
                if await request.is_disconnected():
                    break
                if interval > 0 and (time.time() - last_ping) >= interval:
                    yield (
                        "event: ping\n"
                        + "data: "
                        + json.dumps({"type": "ping", "ts": int(time.time() * 1000)})
                        + "\n\n"
                    )
                    last_ping = time.time()
                phase = update.get("step")
                if phase:
                    name_map = {
                        "retrieval": "retrieve",
                        "rerank": "rerank",
                        "grade": "grade",
                        "web_search": "web_search",
                        "generation": "generate",
                        "generate": "generate",
                        "hallucination": "hallucination",
                        "execute": "execute",
                    }
                    nm = name_map.get(str(phase), str(phase))
                    payload = {"type": "phase", "name": nm, "status": "end"}
                    metrics = update.get("metrics") or {}
                    if nm == "retrieve":
                        m = metrics.get("retrieve") or {}
                        if "count" in m:
                            payload["count"] = int(m.get("count") or 0)
                    elif nm == "rerank":
                        m = metrics.get("rerank") or {}
                        if "avg_score" in m:
                            payload["avg_score"] = float(m.get("avg_score") or 0.0)
                    elif nm == "generate":
                        m = metrics.get("generate") or {}
                        if "context_len" in m:
                            payload["gen_chars"] = int(m.get("context_len") or 0)
                    yield "data: " + json.dumps(payload) + "\n\n"
                if update.get("retrieved_chunks"):
                    chunks = update.get("retrieved_chunks") or []
                    try:
                        for c in (chunks or [])[: meta.get("top_k", 5)]:
                            citation_payload = {
                                "doc_id": c.get("doc_id"),
                                "page": int(c.get("page_num") or 0),
                                "bbox": (c.get("metadata") or {}).get("bbox"),
                                "chunk_id": c.get("id"),
                                "score": float(c.get("rerank_score") or c.get("score") or 0.0),
                                "block_type": (c.get("metadata") or {}).get("block_type")
                                or (c.get("metadata") or {}).get("type"),
                                "heading_level": (c.get("metadata") or {}).get("heading_level"),
                                "table_id": (c.get("metadata") or {}).get("table_id"),
                            }
                            yield (
                                "data: "
                                + json.dumps({"type": "citation", **citation_payload})
                                + "\n\n"
                            )
                    except Exception:
                        pass
                if update.get("context"):
                    context = update.get("context") or context
                if update.get("sources"):
                    final_sources = update.get("sources") or final_sources
                if update.get("answer"):
                    final_answer = update.get("answer")
                    yield "data: " + json.dumps({"type": "answer", "delta": final_answer}) + "\n\n"
            final = {
                "type": "final",
                "sources": sources or final_sources,
                "conversation_id": req.conversation_id or str(uuid4()),
                "answer": final_answer,
            }
            yield "data: " + json.dumps(final) + "\n\n"
        finally:
            if _SSE_SEM and sem_acquired:
                _SSE_SEM.release()
            if _SSE_SEM:
                _METRICS["sse_active"] = max(0, _METRICS.get("sse_active", 0) - 1)
            if _PROM_SSE_ACTIVE:
                try:
                    _PROM_SSE_ACTIVE.dec()
                except Exception:
                    pass

    return StreamingResponse(
        event_gen(), media_type="text/event-stream", headers={"Connection": "close"}
    )


@router.get("/metrics/usage")
async def metrics_usage():
    base = settings.usage_dir_resolved
    path = os.path.join(base, "usage.jsonl")
    os.makedirs(base, exist_ok=True)
    agg: dict[str, dict[str, dict[str, int]]] = {}
    summary: dict[str, dict[str, float]] = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line.strip())
                        day = datetime.utcfromtimestamp(rec.get("ts", int(time.time()))).strftime(
                            "%Y-%m-%d"
                        )
                        prov = rec.get("provider") or "unknown"
                        mdl = rec.get("model") or "unknown"
                        d = agg.setdefault(day, {}).setdefault(
                            f"{prov}:{mdl}",
                            {"calls": 0, "tokens_in": 0, "tokens_out": 0, "duration_ms": 0},
                        )
                        d["calls"] += 1
                        d["tokens_in"] += int(rec.get("tokens_in") or 0)
                        d["tokens_out"] += int(rec.get("tokens_out") or 0)
                        d["duration_ms"] += int(rec.get("duration_ms") or 0)
                        s = summary.setdefault(
                            day, {"calls": 0.0, "tokens": 0.0, "duration_ms": 0.0}
                        )
                        s["calls"] += 1
                        s["tokens"] += int(rec.get("tokens_in") or 0) + int(
                            rec.get("tokens_out") or 0
                        )
                        s["duration_ms"] += int(rec.get("duration_ms") or 0)
                    except Exception:
                        continue
        except Exception:
            pass
    return {"usage": agg, "summary": summary}


@router.post("/alerts/thresholds")
async def set_thresholds(payload: dict):
    base = settings.usage_dir_resolved
    path = os.path.join(base, "thresholds.json")
    os.makedirs(base, exist_ok=True)
    cfg = {
        "max_tokens_per_day": int(
            payload.get("max_tokens_per_day") or getattr(settings, "max_tokens_per_day", 0) or 0
        ),
        "max_calls_per_day": int(
            payload.get("max_calls_per_day") or getattr(settings, "max_calls_per_day", 0) or 0
        ),
        "max_cost_per_day": float(
            payload.get("max_cost_per_day") or getattr(settings, "max_cost_per_day", 0.0) or 0.0
        ),
        "webhook_url": payload.get("webhook_url")
        or getattr(settings, "alert_webhook_url", os.environ.get("ALERT_WEBHOOK_URL")),
    }
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return {"ok": True, "thresholds": cfg}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/alerts/thresholds")
async def get_thresholds():
    base = settings.usage_dir_resolved
    path = os.path.join(base, "thresholds.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
            return {"ok": True, "thresholds": cfg}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "thresholds": {
            "max_tokens_per_day": int(getattr(settings, "max_tokens_per_day", 0) or 0),
            "max_calls_per_day": int(getattr(settings, "max_calls_per_day", 0) or 0),
            "max_cost_per_day": float(getattr(settings, "max_cost_per_day", 0.0) or 0.0),
            "webhook_url": getattr(
                settings, "alert_webhook_url", os.environ.get("ALERT_WEBHOOK_URL")
            ),
        },
    }


@secure_router.get("/metrics/runtime")
async def metrics_runtime(user: dict[str, Any] = Depends(get_current_user)):
    data = {
        "uploads_dir": settings.uploads_dir_resolved,
        "rate_limit_enabled": getattr(settings, "rate_limit_enabled_resolved", False),
        "rate_limit_backend": "redis" if settings.redis_url else "memory",
        "sse_max_connections": int(getattr(settings, "sse_max_connections", 0) or 0),
        "sse_active": int(_METRICS.get("sse_active", 0)),
        "uploads": {
            "ok": int(_METRICS.get("uploads_ok", 0)),
            "rejected": int(_METRICS.get("uploads_reject", 0)),
            "scan_fail": int(_METRICS.get("uploads_scan_fail", 0)),
        },
        "web_search": {
            "provider": getattr(settings, "web_search_provider", None),
            "enabled": getattr(settings, "web_search_enabled", True),
        },
    }
    return {"code": 0, "message": "ok", "data": data}


@router.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...), index: bool = False, kb_name: str | None = None):
    return {"status": "error", "message": "deprecated, use /api/ingest/upload_run"}


@router.post("/ingest/pdf/stream")
async def ingest_pdf_stream(
    request: Request, file: UploadFile = File(...), index: bool = False, kb_name: str | None = None
):
    async def event_gen():
        yield "data: " + json.dumps({"status": "error", "message": "deprecated, use /api/ingest/upload_run/stream"}) + "\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers={"Connection": "close"})


def _md_table_to_csv(md: str) -> str:
    lines = [line.strip() for line in (md or "").splitlines() if line.strip()]
    rows = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            parts = [p.strip() for p in line.split("|")][1:-1]
            if all(set(p) <= set("-: ") for p in parts):
                continue
            rows.append(parts)
    csv_lines = []
    for r in rows:
        csv_lines.append(",".join([p.replace(",", " ") for p in r]))
    return "\n".join(csv_lines)


@router.post("/execute/export")
async def export_csv(payload: dict):
    tables = payload.get("tables") or []
    out_parts = []
    for t in tables:
        out_parts.append(_md_table_to_csv(t or ""))
    return {"csv": "\n\n".join(out_parts)}


@router.post("/execute/export/save")
async def export_csv_save(payload: dict):
    tables = payload.get("tables") or []
    out_parts = []
    for t in tables:
        out_parts.append(_md_table_to_csv(t or ""))
    csv_text = "\n\n".join(out_parts)
    base = settings.uploads_dir_resolved
    out_dir = os.path.join(base, "exports")
    os.makedirs(out_dir, exist_ok=True)
    name = f"{uuid4()}.csv"
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_text)
    return {"file": name, "download_url": f"/api/exports/{name}"}


@router.get("/exports/{name}")
async def download_export(name: str):
    base = settings.uploads_dir_resolved
    path = os.path.join(base, "exports", name)
    if not os.path.exists(path):
        return {"status": "error", "message": "not found"}
    return FileResponse(path, filename=name, media_type="text/csv")





@router.get("/kb")
async def kb_list():
    cols = list_collections_info() or []
    enriched = []
    names_seen = set()
    for c in cols:
        name = c.get("name") or c.get("collection") or c.get("id")
        names_seen.add(str(name))
        cfg = load_kb_config(str(name))
        enriched.append({"name": name, "stats": c, "config": cfg})
    # also include configs without collections
    try:
        import os

        base = settings.uploads_dir_resolved
        kb_dir = os.path.join(base, "knowledgebase")
        if os.path.isdir(kb_dir):
            for fname in os.listdir(kb_dir):
                if not fname.endswith(".json"):
                    continue
                nm = fname[:-5]
                if nm in names_seen:
                    continue
                cfg = load_kb_config(nm)
                enriched.append({"name": nm, "stats": {"name": nm}, "config": cfg})
    except Exception:
        pass
    return {"kbs": enriched}


@router.post("/kb/create")
async def kb_create(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "name_required"}
    # initialize config
    cfg = save_kb_config(name, payload or {})
    # initialize docs registry
    try:
        base = settings.uploads_dir_resolved
        kb_dir = os.path.join(base, "knowledgebase")
        os.makedirs(kb_dir, exist_ok=True)
        reg = os.path.join(kb_dir, f"{name}.docs.json")
        if not os.path.exists(reg):
            with open(reg, "w", encoding="utf-8") as f:
                json.dump({"docs": []}, f)
    except Exception:
        pass
    # optionally create vector collection for Milvus
    try:
        backend = (cfg.get("vector_backend") or "").lower()
        collection_name = (cfg.get("collection_name") or "") or None
        if backend == "milvus" and collection_name:
            from core.storage.milvus_store import MilvusStore

            s = MilvusStore(dim=256, collection_name=collection_name)
            s.try_init()
    except Exception:
        pass
    return {"ok": True, "config": cfg}


@router.get("/kb/{name}/config")
async def kb_get_config(name: str):
    cfg = load_kb_config(name)
    effective = merge_kb_params({"kb_name": name})
    return {"config": cfg, "effective_config": effective}


@router.post("/kb/{name}/config")
async def kb_set_config(name: str, payload: dict[str, Any]):
    cfg = save_kb_config(name, payload or {})
    effective = merge_kb_params({"kb_name": name})
    return {"ok": True, "config": cfg, "effective_config": effective}


@router.post("/kb/{name}/config/reset")
async def kb_reset_config(name: str):
    from core.storage.kb_config import save_kb_config

    base = default_kb_config(name)
    cfg = save_kb_config(name, base)
    effective = merge_kb_params({"kb_name": name})
    effective.update(
        {
            "embedding_model": cfg.get("embedding_model"),
            "stack": cfg.get("stack"),
            "visibility": cfg.get("visibility"),
        }
    )
    base_chunk = (default_kb_config(name) or {}).get("chunk_strategy", {}) or {}
    cfg_chunk = (cfg or {}).get("chunk_strategy", {}) or {}
    merged_chunk = {**base_chunk, **cfg_chunk}
    effective["chunk_strategy"] = merged_chunk
    return {"ok": True, "config": cfg, "effective_config": effective}


@router.get("/kb/pipeline/registry")
async def kb_pipeline_registry():
    return get_pipeline_registry()


@router.get("/kb/pipeline/registry/full")
async def kb_pipeline_registry_full():
    return {
        "ingestion": get_pipeline_registry(),
        "scenarios": get_rag_scenario_pipelines(),
    }


@router.post("/kb/{name}/graph/build")
async def kb_graph_build(name: str):
    cfg = load_kb_config(name)
    method = str(cfg.get("method") or "light")
    app = create_graphrag_light_graph()
    res = await app.ainvoke(
        {"kb_name": name, "method": method, "chunks": [], "graph": {}, "meta": {}}
    )
    kg = dict(cfg.get("knowledge_graph") or {})
    kg["enabled"] = True
    kg["status"] = "completed"
    kg["graph_path"] = (res.get("meta") or {}).get("graph_path")
    cfg["knowledge_graph"] = kg
    save_kb_config(name, cfg)
    return {"ok": True, "status": "completed", "graph_path": kg.get("graph_path")}


@router.get("/kb/{name}/graph/status")
async def kb_graph_status(name: str):
    cfg = load_kb_config(name)
    s = ((cfg.get("knowledge_graph") or {}).get("status")) or "idle"
    return {"status": s}


@router.post("/kb/{name}/raptor/generate")
async def kb_raptor_generate(name: str, payload: dict[str, Any] | None = None):
    payload = payload or {}
    cfg = load_kb_config(name)
    rp = dict(cfg.get("raptor") or {})
    if "scope" in payload:
        rp["scope"] = payload.get("scope")
    if "prompt" in payload:
        rp["prompt"] = payload.get("prompt")
    if "max_tokens" in payload:
        try:
            rp["max_tokens"] = int(payload.get("max_tokens"))
        except Exception:
            pass
    if "threshold" in payload:
        try:
            rp["threshold"] = float(payload.get("threshold"))
        except Exception:
            pass
    if "max_clusters" in payload:
        try:
            rp["max_clusters"] = int(payload.get("max_clusters"))
        except Exception:
            pass
    if "seed" in payload:
        try:
            rp["seed"] = int(payload.get("seed"))
        except Exception:
            pass
    if "file_id" in payload:
        rp["file_id"] = payload.get("file_id")
    app = create_raptor_light_graph()
    res = await app.ainvoke(
        {
            "kb_name": name,
            "scope": str(rp.get("scope") or "whole"),
            "prompt": str(rp.get("prompt") or ""),
            "max_tokens": int(rp.get("max_tokens") or 256),
            "threshold": float(rp.get("threshold") or 0.1),
            "max_clusters": int(rp.get("max_clusters") or 8),
            "seed": int(rp.get("seed") or 0),
            "file_id": rp.get("file_id"),
            "chunks": [],
            "layers": [],
            "summaries": [],
            "meta": {},
        }
    )
    rp["enabled"] = True
    rp["status"] = "completed"
    rp["raptor_path"] = (res.get("meta") or {}).get("raptor_path")
    cfg["raptor"] = rp
    save_kb_config(name, cfg)
    return {"ok": True, "status": "completed", "raptor_path": rp.get("raptor_path")}


@router.get("/kb/{name}/raptor/status")
async def kb_raptor_status(name: str):
    cfg = load_kb_config(name)
    s = ((cfg.get("raptor") or {}).get("status")) or "idle"
    return {"status": s}


@router.post("/kb/{name}/raptor/generate/deep")
async def kb_raptor_generate_deep(name: str, payload: dict[str, Any] | None = None):
    payload = payload or {}
    app = create_raptor_deep_graph()
    t0 = time.perf_counter()
    res = await app.ainvoke(
        {
            "kb_name": name,
            "prompt": str(payload.get("prompt") or ""),
            "max_token": int(payload.get("max_tokens") or 512),
            "threshold": float(payload.get("threshold") or 0.1),
            "max_cluster": int(payload.get("max_clusters") or 8),
            "random_seed": int(payload.get("seed") or 0),
            "chunks": [],
            "layers": [],
            "summaries": [],
            "meta": {},
        }
    )
    dur = int((time.perf_counter() - t0) * 1000)
    cfg = load_kb_config(name)
    rp = dict(cfg.get("raptor") or {})
    rp["enabled"] = True
    rp["status"] = "completed"
    rp["raptor_path_deep"] = (res.get("meta") or {}).get("raptor_path_deep")
    cfg["raptor"] = rp
    save_kb_config(name, cfg)
    return {
        "ok": True,
        "status": "completed",
        "raptor_path_deep": rp.get("raptor_path_deep"),
        "summary_count": int((res.get("meta") or {}).get("summary_count") or 0),
        "duration_ms": dur,
    }


@router.get("/kb/{name}/raptor/compare")
async def kb_raptor_compare(name: str):
    t0 = time.perf_counter()
    light = await create_raptor_light_graph().ainvoke(
        {
            "kb_name": name,
            "scope": "whole",
            "prompt": "",
            "max_tokens": 256,
            "threshold": 0.1,
            "max_clusters": 8,
            "seed": 0,
            "file_id": None,
            "chunks": [],
            "layers": [],
            "summaries": [],
            "meta": {},
        }
    )
    t_light = int((time.perf_counter() - t0) * 1000)
    t1 = time.perf_counter()
    deep = await create_raptor_deep_graph().ainvoke(
        {
            "kb_name": name,
            "prompt": "",
            "max_token": 512,
            "threshold": 0.1,
            "max_cluster": 8,
            "random_seed": 0,
            "chunks": [],
            "layers": [],
            "summaries": [],
            "meta": {},
        }
    )
    t_deep = int((time.perf_counter() - t1) * 1000)
    return {
        "light": {
            "summaries": len(light.get("summaries") or []),
            "duration_ms": t_light,
            "path": (light.get("meta") or {}).get("raptor_path"),
        },
        "deep": {
            "summaries": len(deep.get("summaries") or []),
            "duration_ms": t_deep,
            "path": (deep.get("meta") or {}).get("raptor_path_deep"),
        },
        "samples": {
            "light_summaries": (light.get("summaries") or [])[:3],
            "deep_summaries": (deep.get("summaries") or [])[:3],
        },
    }


@router.post("/kb/{name}/mindmap/build")
async def kb_mindmap_build(name: str):
    app = create_mindmap_light_graph()
    res = await app.ainvoke({"kb_name": name, "outline": {}, "meta": {}})
    cfg = load_kb_config(name)
    mm = dict(cfg.get("mindmap") or {})
    mm["enabled"] = True
    mm["status"] = "completed"
    mm["mindmap_path"] = (res.get("meta") or {}).get("mindmap_path")
    cfg["mindmap"] = mm
    save_kb_config(name, cfg)
    return {"ok": True, "status": "completed", "mindmap_path": mm.get("mindmap_path")}


@router.get("/kb/{name}/mindmap/status")
async def kb_mindmap_status(name: str):
    cfg = load_kb_config(name)
    s = ((cfg.get("mindmap") or {}).get("status")) or "idle"
    return {"status": s}


@router.post("/kb/{name}/graph/build/deep")
async def kb_graph_build_deep(name: str):
    app = create_graphrag_deep_graph()
    t0 = time.perf_counter()
    res = await app.ainvoke(
        {
            "kb_name": name,
            "language": None,
            "entity_types": None,
            "chunks": [],
            "graph": {},
            "meta": {},
        }
    )
    dur = int((time.perf_counter() - t0) * 1000)
    cfg = load_kb_config(name)
    kg = dict(cfg.get("knowledge_graph") or {})
    kg["enabled"] = True
    kg["status"] = "completed"
    kg["graph_path_deep"] = (res.get("meta") or {}).get("graph_path_deep")
    cfg["knowledge_graph"] = kg
    save_kb_config(name, cfg)
    return {
        "ok": True,
        "status": "completed",
        "graph_path_deep": kg.get("graph_path_deep"),
        "node_count": int((res.get("meta") or {}).get("node_count") or 0),
        "edge_count": int((res.get("meta") or {}).get("edge_count") or 0),
        "duration_ms": dur,
    }


@router.get("/kb/{name}/graph/compare")
async def kb_graph_compare(name: str):
    t0 = time.perf_counter()
    light = await create_graphrag_light_graph().ainvoke(
        {"kb_name": name, "method": "light", "chunks": [], "graph": {}, "meta": {}}
    )
    t_light = int((time.perf_counter() - t0) * 1000)
    t1 = time.perf_counter()
    deep = await create_graphrag_deep_graph().ainvoke(
        {
            "kb_name": name,
            "language": None,
            "entity_types": None,
            "chunks": [],
            "graph": {},
            "meta": {},
        }
    )
    t_deep = int((time.perf_counter() - t1) * 1000)
    lg = light.get("graph") or {}
    dg = deep.get("graph") or {}
    return {
        "light": {
            "nodes": len(lg.get("nodes", [])),
            "edges": len(lg.get("edges", [])),
            "duration_ms": t_light,
            "path": (light.get("meta") or {}).get("graph_path"),
        },
        "deep": {
            "nodes": len(dg.get("nodes", [])),
            "edges": len(dg.get("edges", [])),
            "duration_ms": t_deep,
            "path": (deep.get("meta") or {}).get("graph_path_deep"),
        },
        "samples": {
            "light_nodes": (lg.get("nodes", []) or [])[:3],
            "deep_nodes": (dg.get("nodes", []) or [])[:3],
            "light_edges": (lg.get("edges", []) or [])[:3],
            "deep_edges": (dg.get("edges", []) or [])[:3],
        },
    }


@router.get("/kb/{name}/documents")
async def kb_documents(name: str):
    uploads_dir = settings.uploads_dir_resolved
    metas = []
    try:
        from core.storage.index_router import list_all_meta

        metas = list_all_meta() or []
    except Exception:
        metas = []
    doc_ids = []
    seen = set()
    for m in metas:
        kb = m.get("kb_name") or (m.get("metadata", {}) or {}).get("kb_name")
        if str(kb or "") != str(name):
            continue
        did = m.get("doc_id")
        if not did or did in seen:
            continue
        seen.add(did)
        doc_ids.append(did)
    items = []
    for did in doc_ids:
        pdf_path = (
            did
            if (isinstance(did, str) and os.path.isabs(did))
            else os.path.join(uploads_dir, f"{did}.pdf")
        )
        try:
            stat = os.stat(pdf_path)
            file_size = stat.st_size
        except Exception:
            file_size = 0
        s = doc_stats(pdf_path)
        items.append(
            {
                "id": did,
                "filename": os.path.basename(pdf_path),
                "processing_status": "completed" if os.path.exists(pdf_path) else "missing",
                "processed_pages": int(s.get("processed_pages") or 0),
                "total_pages": 0,
                "file_size": file_size,
            }
        )
    # fallback from docs registry
    try:
        reg = os.path.join(uploads_dir, "knowledgebase", f"{name}.docs.json")
        if os.path.exists(reg):
            with open(reg, encoding="utf-8") as f:
                docs = (json.load(f) or {}).get("docs") or []
            ids_existing = {x.get("id") for x in items}
            for d in docs:
                did = d.get("id")
                if not did or did in ids_existing:
                    continue
                fpath = d.get("path") or os.path.join(uploads_dir, f"{did}.pdf")
                try:
                    stat = os.stat(fpath)
                    file_size = stat.st_size
                except Exception:
                    file_size = 0
                items.append(
                    {
                        "id": did,
                        "filename": d.get("filename") or os.path.basename(fpath),
                        "processing_status": "completed" if os.path.exists(fpath) else "missing",
                        "processed_pages": 0,
                        "total_pages": 0,
                        "file_size": file_size,
                    }
                )
    except Exception:
        pass
    return {"documents": items}
