import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from core.algorithms.graphrag import GraphRAGProcessor
from core.algorithms.raptor import unified_raptor_process
from core.ingestion.graph import create_ingest_graph
from core.state import IngestState, StrategyConfig
from core.storage.blob_store import get_blob_store
from core.utils.trace import set_span_attrs

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

if prometheus_client:
    _C_INGEST_EVENTS = prometheus_client.Counter(
        "ingest_sse_events_total", "Ingest SSE events", ["type"]
    )
else:
    _C_INGEST_EVENTS = None


def _emit(event: dict) -> str:
    if _C_INGEST_EVENTS:
        try:
            _C_INGEST_EVENTS.labels(event.get("type") or "unknown").inc()
        except Exception:
            pass
    return f"data: {json.dumps(event)}\n\n"


router = APIRouter()

# 场景化策略预设
SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "laws": {
        "chunking": {"mode": "fixed", "chunk_size": 800, "chunk_overlap": 80},
        "ocr_provider": "auto",
        "force_ocr": False,
    },
    "paper": {
        "chunking": {"mode": "fixed", "chunk_size": 1200, "chunk_overlap": 120},
        "ocr_provider": "auto",
        "force_ocr": False,
    },
    "table": {
        "chunking": {"mode": "table_first", "chunk_size": 800, "chunk_overlap": 80},
        "ocr_provider": "auto",
        "force_ocr": True,
    },
    "html": {
        "chunking": {"mode": "fixed", "chunk_size": 600, "chunk_overlap": 60},
        "ocr_provider": "auto",
        "force_ocr": False,
    },
}


@router.get("/scenarios")
async def list_scenarios():
    return {"scenarios": SCENARIO_PRESETS}


@router.post("/run")
async def run_ingest(request: Request):
    body = await request.json()

    # Defaults
    task_id = body.get("task_id") or str(uuid.uuid4())
    kb_name = body.get("kb_name", "default")

    # Config：合并场景预设
    config_dict = body.get("strategy_config", {}) or {}
    scenario = body.get("scenario")
    if scenario and scenario in SCENARIO_PRESETS:
        merged = {**SCENARIO_PRESETS[scenario], **config_dict}
    else:
        merged = config_dict
    strategy_config = StrategyConfig(**merged).dict()

    initial_state = IngestState(
        channel_id=body.get("channel_id", "default"),
        task_id=task_id,
        file_path=body["file_path"],
        file_type=body.get("file_type", "pdf"),
        batch_id=body.get("batch_id", str(uuid.uuid4())),
        kb_name=kb_name,
        version=body.get("version", 1),
        strategy_config=strategy_config,
        capability_loader=None,  # TODO: Load capabilities via prepare_kb_capabilities
        processing_stage="upload",
        retry_count=0,
        error_log=[],
        progress={"total_chunks": 0, "completed_chunks": 0},
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        quality_metrics={},
    )

    app = create_ingest_graph()

    async def event_generator():
        try:
            async for event in app.astream_events(initial_state, version="v1"):
                event_type = event["event"]

                if event_type == "on_chain_start":
                    yield _emit({"type": "node_start", "node": event["name"]})

                elif event_type == "on_chain_end":
                    yield _emit({"type": "node_end", "node": event["name"]})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            set_span_attrs({"ingest.error": str(e)})
            yield _emit({"type": "error", "error": str(e)})

        algo_cfg = strategy_config.get("algorithms", {})
        if algo_cfg.get("enable_raptor"):
            yield _emit({"type": "node_start", "node": "raptor_clustering"})
            try:
                unified_raptor_process(kb_name)
                yield _emit({"type": "node_end", "node": "raptor_clustering"})
            except Exception as e:
                set_span_attrs({"ingest.raptor.error": str(e)})
                yield _emit({"type": "error", "node": "raptor", "error": str(e)})

        if algo_cfg.get("enable_graphrag"):
            yield _emit({"type": "node_start", "node": "graphrag_construction"})
            try:
                GraphRAGProcessor(kb_name)
                yield _emit({"type": "node_end", "node": "graphrag_construction"})
            except Exception as e:
                set_span_attrs({"ingest.graphrag.error": str(e)})
                yield _emit({"type": "error", "node": "graphrag", "error": str(e)})

        yield _emit({"type": "complete"})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/upload_run")
async def upload_and_run_ingest(
    file: UploadFile = File(...),
    kb_name: str | None = None,
    scenario: str | None = None,
    strategy_config: dict | None = None,
    version: int = 1,
):
    """
    便捷上传并走新 LangGraph ingest 的入口，供前端替换旧 /ingest/* 路由。
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    ext = (os.path.splitext(file.filename or "")[1] or "").lower().lstrip(".") or "pdf"
    file_type = ext
    blob = get_blob_store()
    key = f"uploads/{uuid.uuid4()}_{file.filename or 'file'}"
    await blob.put(key, content)

    # 合并场景策略
    config_dict = strategy_config or {}
    if isinstance(config_dict, str):
        try:
            config_dict = json.loads(config_dict)
        except Exception:
            config_dict = {}
    if scenario and scenario in SCENARIO_PRESETS:
        config_dict = {**SCENARIO_PRESETS[scenario], **config_dict}
    strategy = StrategyConfig(**config_dict).dict()

    initial_state = IngestState(
        channel_id="default",  # TODO: Get from request context
        task_id=str(uuid.uuid4()),
        file_path=key,
        file_type=file_type,
        batch_id=str(uuid.uuid4()),
        kb_name=kb_name or "default",
        version=version,
        strategy_config=strategy,
        capability_loader=None,  # TODO: Load capabilities via prepare_kb_capabilities
        processing_stage="upload",
        retry_count=0,
        error_log=[],
        progress={"total_chunks": 0, "completed_chunks": 0},
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        quality_metrics={},
    )

    app = create_ingest_graph()
    res = await app.ainvoke(
        initial_state, config={"configurable": {"thread_id": initial_state["task_id"]}}
    )
    return {
        "task_id": initial_state["task_id"],
        "kb_name": kb_name or "default",
        "file_path": key,
        "chunks": res.get("chunks"),
        "md": res.get("md") or None,
        "md_path": (res.get("meta") or {}).get("md_path") if isinstance(res, dict) else None,
        "progress": res.get("progress") if isinstance(res, dict) else None,
    }


@router.post("/upload_run/stream")
async def upload_and_run_ingest_stream(
    file: UploadFile = File(...),
    kb_name: str | None = None,
    scenario: str | None = None,
    strategy_config: dict | None = None,
    version: int = 1,
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    ext = (os.path.splitext(file.filename or "")[1] or "").lower().lstrip(".") or "pdf"
    file_type = ext
    blob = get_blob_store()
    key = f"uploads/{uuid.uuid4()}_{file.filename or 'file'}"
    await blob.put(key, content)

    config_dict = strategy_config or {}
    if isinstance(config_dict, str):
        try:
            config_dict = json.loads(config_dict)
        except Exception:
            config_dict = {}
    if scenario and scenario in SCENARIO_PRESETS:
        config_dict = {**SCENARIO_PRESETS[scenario], **config_dict}
    strategy = StrategyConfig(**config_dict).dict()

    initial_state = IngestState(
        channel_id="default",  # TODO: Get from request context
        task_id=str(uuid.uuid4()),
        file_path=key,
        file_type=file_type,
        batch_id=str(uuid.uuid4()),
        kb_name=kb_name or "default",
        version=version,
        strategy_config=strategy,
        capability_loader=None,  # TODO: Load capabilities via prepare_kb_capabilities
        processing_stage="upload",
        retry_count=0,
        error_log=[],
        progress={"total_chunks": 0, "completed_chunks": 0},
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        quality_metrics={},
    )

    app = create_ingest_graph()

    async def event_generator():
        try:
            async for event in app.astream_events(initial_state, version="v1"):
                et = event.get("event")
                name = event.get("name")
                if et == "on_chain_start":
                    yield f"data: {json.dumps({'type': 'node_start', 'node': name})}\n\n"
                elif et == "on_chain_end":
                    yield f"data: {json.dumps({'type': 'node_end', 'node': name})}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            set_span_attrs({"ingest.stream.error": str(e)})
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'complete', 'task_id': initial_state['task_id']})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
