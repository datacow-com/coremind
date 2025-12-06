import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from core.state import RetrievalState
from core.retrieval.graph import create_qa_graph

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
        retrieved_chunks=[], # legacy compat
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
    
    async def event_generator():
        async for event in app.astream_events(initial_state, version="v1"):
            event_type = event['event']
            
            if event_type == "on_chain_start":
                yield f"data: {json.dumps({'type': 'node_start', 'node': event['name']})}\n\n"
            elif event_type == "on_chain_end":
                yield f"data: {json.dumps({'type': 'node_end', 'node': event['name']})}\n\n"
            
            # Stream final answer token by token? 
            # Astream_events might stream internal LLM events if nested.
            # For now, we might just yield final result or state updates.
            
            # If generator node outputs, we can capture it
            if event['name'] == 'generator' and event_type == 'on_chain_end':
                output = event['data'].get('output', {})
                if output.get('final_answer'):
                    yield f"data: {json.dumps({'type': 'answer', 'content': output['final_answer'], 'citations': output['citations']})}\n\n"

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

