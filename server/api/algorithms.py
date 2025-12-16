"""
Algorithms API - 算法执行 API

提供高级算法（RAPTOR, GraphRAG, MindMap）的执行和监控接口：
- POST /api/algorithms/raptor/run - 启动 RAPTOR 任务
- POST /api/algorithms/graphrag/run - 启动 GraphRAG 任务
- POST /api/algorithms/mindmap/run - 启动 MindMap 任务
- GET /api/algorithms/{task_id}/status - 获取任务状态
- GET /api/algorithms/{task_id}/progress - SSE 进度流
- GET /api/algorithms/history - 获取执行历史

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 8.6, 11.1, 11.2, 11.5
"""

import asyncio
import json
import time
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Enums and Constants
# ═══════════════════════════════════════════════════════════════════════════════


class AlgorithmType(str, Enum):
    """Supported algorithm types."""

    RAPTOR = "raptor"
    GRAPHRAG = "graphrag"
    MINDMAP = "mindmap"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AlgorithmMode(str, Enum):
    """Algorithm execution mode."""

    LIGHT = "light"
    DEEP = "deep"


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════════


class AlgorithmRunRequest(BaseModel):
    """Request model for starting an algorithm task."""

    kb_name: str = Field(..., description="Target knowledge base name")
    mode: AlgorithmMode = Field(default=AlgorithmMode.LIGHT, description="Execution mode: light or deep")
    config: dict[str, Any] = Field(default_factory=dict, description="Algorithm-specific configuration")


class RaptorConfig(BaseModel):
    """RAPTOR-specific configuration."""

    max_clusters: int = Field(default=4, ge=1, le=20, description="Maximum clusters per level")
    levels: int = Field(default=3, ge=1, le=10, description="Number of hierarchy levels")
    summary_max_tokens: int = Field(default=150, ge=50, le=1000, description="Max tokens per summary")
    threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Clustering threshold")


class GraphRAGConfig(BaseModel):
    """GraphRAG-specific configuration."""

    entity_types: list[str] = Field(
        default_factory=lambda: ["人物", "组织", "地点"],
        description="Entity types to extract",
    )
    language: str = Field(default="zh", description="Language for extraction")
    community_detection: bool = Field(default=True, description="Enable community detection")


class MindMapConfig(BaseModel):
    """MindMap-specific configuration."""

    max_topics: int = Field(default=10, ge=1, le=50, description="Maximum number of topics")
    depth: int = Field(default=3, ge=1, le=5, description="Maximum depth of topic hierarchy")


class AlgorithmTask(BaseModel):
    """Algorithm task model."""

    task_id: str = Field(..., description="Unique task identifier")
    algorithm: AlgorithmType = Field(..., description="Algorithm type")
    kb_name: str = Field(..., description="Target knowledge base")
    mode: AlgorithmMode = Field(..., description="Execution mode")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    stage: str = Field(default="", description="Current processing stage")
    config: dict[str, Any] = Field(default_factory=dict, description="Task configuration")
    created_at: str = Field(..., description="Creation timestamp")
    started_at: str | None = Field(default=None, description="Start timestamp")
    completed_at: str | None = Field(default=None, description="Completion timestamp")
    error: str | None = Field(default=None, description="Error message if failed")
    result: dict[str, Any] | None = Field(default=None, description="Task result")
    estimated_cost: float = Field(default=0.0, description="Estimated cost in tokens")
    actual_cost: float | None = Field(default=None, description="Actual cost in tokens")


class AlgorithmProgress(BaseModel):
    """Progress event model for SSE."""

    task_id: str
    stage: str
    progress: int = Field(ge=0, le=100)
    message: str
    timestamp: str


class TaskRunResponse(BaseModel):
    """Response for starting a task."""

    task_id: str
    algorithm: AlgorithmType
    kb_name: str
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status query."""

    task: AlgorithmTask


class HistoryResponse(BaseModel):
    """Response for execution history."""

    tasks: list[AlgorithmTask]
    total: int
    page: int
    page_size: int


# ═══════════════════════════════════════════════════════════════════════════════
# In-Memory Task Store (for MVP - should be replaced with DB persistence)
# ═══════════════════════════════════════════════════════════════════════════════

_task_store: dict[str, AlgorithmTask] = {}
_task_progress: dict[str, list[AlgorithmProgress]] = {}
_progress_subscribers: dict[str, list[asyncio.Queue]] = {}


def get_task(task_id: str) -> AlgorithmTask | None:
    """Get task by ID."""
    return _task_store.get(task_id)


def save_task(task: AlgorithmTask) -> None:
    """Save task to store."""
    _task_store[task.task_id] = task


def list_tasks(
    kb_name: str | None = None,
    algorithm: AlgorithmType | None = None,
    status: TaskStatus | None = None,
) -> list[AlgorithmTask]:
    """List tasks with optional filters."""
    tasks = list(_task_store.values())

    if kb_name:
        tasks = [t for t in tasks if t.kb_name == kb_name]
    if algorithm:
        tasks = [t for t in tasks if t.algorithm == algorithm]
    if status:
        tasks = [t for t in tasks if t.status == status]

    # Sort by created_at descending
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return tasks


def add_progress(task_id: str, progress: AlgorithmProgress) -> None:
    """Add progress event for a task."""
    if task_id not in _task_progress:
        _task_progress[task_id] = []
    _task_progress[task_id].append(progress)

    # Notify subscribers
    if task_id in _progress_subscribers:
        for queue in _progress_subscribers[task_id]:
            try:
                queue.put_nowait(progress)
            except asyncio.QueueFull:
                pass


def get_progress_history(task_id: str) -> list[AlgorithmProgress]:
    """Get progress history for a task."""
    return _task_progress.get(task_id, [])


def subscribe_progress(task_id: str) -> asyncio.Queue:
    """Subscribe to progress updates for a task."""
    if task_id not in _progress_subscribers:
        _progress_subscribers[task_id] = []
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _progress_subscribers[task_id].append(queue)
    return queue


def unsubscribe_progress(task_id: str, queue: asyncio.Queue) -> None:
    """Unsubscribe from progress updates."""
    if task_id in _progress_subscribers:
        try:
            _progress_subscribers[task_id].remove(queue)
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# Cost Estimation
# ═══════════════════════════════════════════════════════════════════════════════


def estimate_cost(algorithm: AlgorithmType, kb_name: str, mode: AlgorithmMode, config: dict) -> float:
    """
    Estimate cost for algorithm execution.

    Cost is proportional to KB size and algorithm complexity.
    Returns estimated tokens.
    """
    # Base cost per algorithm (in tokens)
    base_costs = {
        AlgorithmType.RAPTOR: 5000,
        AlgorithmType.GRAPHRAG: 8000,
        AlgorithmType.MINDMAP: 3000,
    }

    # Mode multiplier
    mode_multiplier = 2.0 if mode == AlgorithmMode.DEEP else 1.0

    # Get KB size estimate (placeholder - should query actual KB)
    # For now, use a default estimate
    kb_size_factor = 1.0

    base = base_costs.get(algorithm, 5000)
    return base * mode_multiplier * kb_size_factor


# ═══════════════════════════════════════════════════════════════════════════════
# Task Execution (Background)
# ═══════════════════════════════════════════════════════════════════════════════


async def execute_raptor_task(task: AlgorithmTask) -> None:
    """Execute RAPTOR algorithm task."""
    from core.algorithms.raptor_deep import create_raptor_deep_graph
    from core.algorithms.raptor_light import create_raptor_light_graph

    try:
        # Update status to running
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow().isoformat() + "Z"
        task.stage = "initializing"
        save_task(task)

        _emit_progress(task, "initializing", 0, "Initializing RAPTOR algorithm...")

        # Select graph based on mode
        if task.mode == AlgorithmMode.DEEP:
            graph = create_raptor_deep_graph()
        else:
            graph = create_raptor_light_graph()

        # Prepare state
        config = task.config
        state = {
            "kb_name": task.kb_name,
            "channel_id": config.get("channel_id", "default"),
            "prompt": config.get("prompt", ""),
            "max_token": config.get("summary_max_tokens", 150),
            "threshold": config.get("threshold", 0.5),
            "max_cluster": config.get("max_clusters", 4 if task.mode == AlgorithmMode.LIGHT else 8),
            "random_seed": config.get("random_seed", 42),
            "chunks": [],
            "layers": [],
            "summaries": [],
            "meta": {},
        }

        _emit_progress(task, "collecting", 20, "Collecting texts from knowledge base...")

        # Execute graph
        result = await graph.ainvoke(state, config={"configurable": {"thread_id": task.task_id}})

        _emit_progress(task, "summarizing", 60, "Generating summaries...")
        await asyncio.sleep(0.1)  # Allow progress to be sent

        _emit_progress(task, "storing", 90, "Storing results...")

        # Update task with results
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.stage = "completed"
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        task.result = {
            "layers_count": len(result.get("layers", [])),
            "summaries_count": len(result.get("summaries", [])),
            "meta": result.get("meta", {}),
        }
        task.actual_cost = task.estimated_cost * 0.9  # Simulated actual cost
        save_task(task)

        _emit_progress(task, "completed", 100, "RAPTOR processing completed successfully")

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        save_task(task)
        _emit_progress(task, "failed", task.progress, f"Error: {str(e)}")


async def execute_graphrag_task(task: AlgorithmTask) -> None:
    """Execute GraphRAG algorithm task."""
    from core.algorithms.graphrag_deep import create_graphrag_deep_graph
    from core.algorithms.graphrag_light import create_graphrag_light_graph

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow().isoformat() + "Z"
        task.stage = "initializing"
        save_task(task)

        _emit_progress(task, "initializing", 0, "Initializing GraphRAG algorithm...")

        if task.mode == AlgorithmMode.DEEP:
            graph = create_graphrag_deep_graph()
        else:
            graph = create_graphrag_light_graph()

        config = task.config
        state = {
            "kb_name": task.kb_name,
            "channel_id": config.get("channel_id", "default"),
            "language": config.get("language", "zh"),
            "entity_types": config.get("entity_types", ["人物", "组织", "地点"]),
            "chunks": [],
            "graph": {},
            "meta": {},
        }

        _emit_progress(task, "collecting", 20, "Collecting texts from knowledge base...")

        result = await graph.ainvoke(state, config={"configurable": {"thread_id": task.task_id}})

        _emit_progress(task, "extracting", 60, "Extracting entities and relations...")
        await asyncio.sleep(0.1)

        _emit_progress(task, "storing", 90, "Storing knowledge graph...")

        graph_result = result.get("graph", {})
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.stage = "completed"
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        task.result = {
            "entities_count": len(graph_result.get("entities", [])),
            "relations_count": len(graph_result.get("relations", [])),
            "meta": result.get("meta", {}),
        }
        task.actual_cost = task.estimated_cost * 0.85
        save_task(task)

        _emit_progress(task, "completed", 100, "GraphRAG processing completed successfully")

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        save_task(task)
        _emit_progress(task, "failed", task.progress, f"Error: {str(e)}")


async def execute_mindmap_task(task: AlgorithmTask) -> None:
    """Execute MindMap algorithm task."""
    from core.algorithms.mindmap_light import create_mindmap_light_graph

    try:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow().isoformat() + "Z"
        task.stage = "initializing"
        save_task(task)

        _emit_progress(task, "initializing", 0, "Initializing MindMap algorithm...")

        graph = create_mindmap_light_graph()

        state = {
            "kb_name": task.kb_name,
            "chunks": [],
            "topics": [],
            "mindmap": {},
            "meta": {},
        }

        _emit_progress(task, "collecting", 20, "Collecting texts from knowledge base...")

        result = await graph.ainvoke(state, config={"configurable": {"thread_id": task.task_id}})

        _emit_progress(task, "extracting", 50, "Extracting topics...")
        await asyncio.sleep(0.1)

        _emit_progress(task, "building", 80, "Building mindmap structure...")

        _emit_progress(task, "storing", 90, "Storing mindmap...")

        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.stage = "completed"
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        task.result = {
            "topics_count": len(result.get("topics", [])),
            "mindmap_path": result.get("meta", {}).get("mindmap_path"),
            "meta": result.get("meta", {}),
        }
        task.actual_cost = task.estimated_cost * 0.8
        save_task(task)

        _emit_progress(task, "completed", 100, "MindMap processing completed successfully")

    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.completed_at = datetime.utcnow().isoformat() + "Z"
        save_task(task)
        _emit_progress(task, "failed", task.progress, f"Error: {str(e)}")


def _emit_progress(task: AlgorithmTask, stage: str, progress: int, message: str) -> None:
    """Emit progress event."""
    task.stage = stage
    task.progress = progress
    save_task(task)

    event = AlgorithmProgress(
        task_id=task.task_id,
        stage=stage,
        progress=progress,
        message=message,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
    add_progress(task.task_id, event)


# ═══════════════════════════════════════════════════════════════════════════════
# Router and Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.post("/raptor/run", response_model=TaskRunResponse)
async def run_raptor(request: AlgorithmRunRequest) -> TaskRunResponse:
    """
    启动 RAPTOR 算法任务

    Requirements: 2.1
    """
    task_id = str(uuid4())
    estimated_cost = estimate_cost(AlgorithmType.RAPTOR, request.kb_name, request.mode, request.config)

    task = AlgorithmTask(
        task_id=task_id,
        algorithm=AlgorithmType.RAPTOR,
        kb_name=request.kb_name,
        mode=request.mode,
        status=TaskStatus.PENDING,
        config=request.config,
        created_at=datetime.utcnow().isoformat() + "Z",
        estimated_cost=estimated_cost,
    )
    save_task(task)

    # Start background execution
    asyncio.create_task(execute_raptor_task(task))

    return TaskRunResponse(
        task_id=task_id,
        algorithm=AlgorithmType.RAPTOR,
        kb_name=request.kb_name,
        status=TaskStatus.PENDING,
        message="RAPTOR task started successfully",
    )


@router.post("/graphrag/run", response_model=TaskRunResponse)
async def run_graphrag(request: AlgorithmRunRequest) -> TaskRunResponse:
    """
    启动 GraphRAG 算法任务

    Requirements: 2.2
    """
    task_id = str(uuid4())
    estimated_cost = estimate_cost(AlgorithmType.GRAPHRAG, request.kb_name, request.mode, request.config)

    task = AlgorithmTask(
        task_id=task_id,
        algorithm=AlgorithmType.GRAPHRAG,
        kb_name=request.kb_name,
        mode=request.mode,
        status=TaskStatus.PENDING,
        config=request.config,
        created_at=datetime.utcnow().isoformat() + "Z",
        estimated_cost=estimated_cost,
    )
    save_task(task)

    asyncio.create_task(execute_graphrag_task(task))

    return TaskRunResponse(
        task_id=task_id,
        algorithm=AlgorithmType.GRAPHRAG,
        kb_name=request.kb_name,
        status=TaskStatus.PENDING,
        message="GraphRAG task started successfully",
    )


@router.post("/mindmap/run", response_model=TaskRunResponse)
async def run_mindmap(request: AlgorithmRunRequest) -> TaskRunResponse:
    """
    启动 MindMap 算法任务

    Requirements: 2.3
    """
    task_id = str(uuid4())
    estimated_cost = estimate_cost(AlgorithmType.MINDMAP, request.kb_name, request.mode, request.config)

    task = AlgorithmTask(
        task_id=task_id,
        algorithm=AlgorithmType.MINDMAP,
        kb_name=request.kb_name,
        mode=request.mode,
        status=TaskStatus.PENDING,
        config=request.config,
        created_at=datetime.utcnow().isoformat() + "Z",
        estimated_cost=estimated_cost,
    )
    save_task(task)

    asyncio.create_task(execute_mindmap_task(task))

    return TaskRunResponse(
        task_id=task_id,
        algorithm=AlgorithmType.MINDMAP,
        kb_name=request.kb_name,
        status=TaskStatus.PENDING,
        message="MindMap task started successfully",
    )


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    获取任务状态

    Requirements: 2.1, 2.2, 2.3
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return TaskStatusResponse(task=task)


@router.get("/{task_id}/progress")
async def get_task_progress(task_id: str) -> StreamingResponse:
    """
    SSE 进度流

    Requirements: 2.4, 11.1, 11.2, 11.5
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    async def event_generator():
        # Send existing progress history first (for reconnection support)
        history = get_progress_history(task_id)
        for event in history:
            yield f"data: {event.model_dump_json()}\n\n"

        # If task is already completed/failed, close connection
        current_task = get_task(task_id)
        if current_task and current_task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            yield f"data: {json.dumps({'type': 'close', 'reason': current_task.status.value})}\n\n"
            return

        # Subscribe to new progress events
        queue = subscribe_progress(task_id)
        try:
            while True:
                try:
                    # Wait for new progress with timeout for heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event.model_dump_json()}\n\n"

                    # Check if task completed
                    if event.stage in ("completed", "failed"):
                        yield f"data: {json.dumps({'type': 'close', 'reason': event.stage})}\n\n"
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f": heartbeat\n\n"

                    # Check if task still exists and is running
                    current = get_task(task_id)
                    if not current or current.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                        yield f"data: {json.dumps({'type': 'close', 'reason': 'task_ended'})}\n\n"
                        break
        finally:
            unsubscribe_progress(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    kb_name: str | None = Query(default=None, description="Filter by KB name"),
    algorithm: AlgorithmType | None = Query(default=None, description="Filter by algorithm type"),
    status: TaskStatus | None = Query(default=None, description="Filter by status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
) -> HistoryResponse:
    """
    获取执行历史

    Requirements: 8.6
    """
    tasks = list_tasks(kb_name=kb_name, algorithm=algorithm, status=status)
    total = len(tasks)

    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = tasks[start:end]

    return HistoryResponse(
        tasks=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )
