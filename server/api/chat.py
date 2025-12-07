import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.retrieval.graph import create_qa_graph
from core.state import RetrievalState
from core.utils.trace import set_span_attrs

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None

if prometheus_client:
    _C_CHAT_EVENTS = prometheus_client.Counter("chat_sse_events_total", "Chat SSE events", ["type"])
else:
    _C_CHAT_EVENTS = None


def _emit(event: dict) -> str:
    if _C_CHAT_EVENTS:
        try:
            _C_CHAT_EVENTS.labels(event.get("type") or "unknown").inc()
        except Exception:
            pass
    return f"data: {json.dumps(event)}\n\n"


router = APIRouter()


@router.post("/run")
async def run_chat(request: Request):
    body = await request.json()

    initial_state = RetrievalState(
        query_id=str(uuid.uuid4()),
        input_query=body.get("query", ""),
        chat_history=body.get("history", []),
        kb_name=body.get("kb_name", "default"),
        user_id=body.get("user_id", "anonymous"),
        strategy_config=body.get("strategy_config", {}),
        preprocessed_queries=[],
        intent={},
        vector_results=[],
        keyword_results=[],
        fused_results=[],
        reranked_results=[],
        retrieved_chunks=[],  # legacy compat
        relevance_score=0.0,
        is_relevant=True,
        loop_count=0,
        answer="",
        final_answer="",
        citations=[],
        confidence=0.0,
        sources=[],
    )

    app = create_qa_graph()

    async def event_generator():
        try:
            async for event in app.astream_events(initial_state, version="v1"):
                event_type = event["event"]

                if event_type == "on_chain_start":
                    yield _emit({"type": "node_start", "node": event["name"]})
                elif event_type == "on_chain_end":
                    yield _emit({"type": "node_end", "node": event["name"]})

                if event["name"] == "generator" and event_type == "on_chain_end":
                    output = event["data"].get("output", {})
                    if output.get("final_answer"):
                        yield _emit(
                            {
                                "type": "answer",
                                "content": output["final_answer"],
                                "citations": output.get("citations", []),
                            }
                        )
            yield _emit({"type": "complete"})
        except asyncio.CancelledError:
            raise
        except Exception as e:
            set_span_attrs({"chat.error": str(e)})
            yield _emit({"type": "error", "error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
