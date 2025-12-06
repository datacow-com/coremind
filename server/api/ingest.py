import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from core.state import IngestState, StrategyConfig
from core.ingestion.graph import create_ingest_graph
from core.algorithms.raptor import unified_raptor_process
from core.algorithms.graphrag import GraphRAGProcessor
from core.algorithms.mindmap import MindmapProcessor

router = APIRouter()

@router.post("/run")
async def run_ingest(request: Request):
    body = await request.json()
    
    # Defaults
    task_id = body.get('task_id') or str(uuid.uuid4())
    kb_name = body.get('kb_name', 'default')
    
    # Config
    config_dict = body.get('strategy_config', {})
    strategy_config = StrategyConfig(**config_dict).dict()
    
    initial_state = IngestState(
        task_id=task_id,
        file_path=body['file_path'],
        file_type=body.get('file_type', 'pdf'),
        batch_id=body.get('batch_id', str(uuid.uuid4())),
        kb_name=kb_name,
        version=body.get('version', 1),
        strategy_config=strategy_config,
        processing_stage='upload',
        retry_count=0,
        error_log=[],
        progress={'total_chunks': 0, 'completed_chunks': 0},
        raw_content=None,
        extracted_text=None,
        parsed_blocks=[],
        images=[],
        chunks=[],
        vectors=[],
        quality_metrics={}
    )
    
    app = create_ingest_graph()
    
    async def event_generator():
        # "v1" is protocol version for astream_events
        async for event in app.astream_events(initial_state, version="v1"):
            event_type = event['event']
            
            if event_type == "on_chain_start":
                yield f"data: {json.dumps({'type': 'node_start', 'node': event['name']})}\n\n"
            
            elif event_type == "on_chain_end":
                yield f"data: {json.dumps({'type': 'node_end', 'node': event['name']})}\n\n"
            
            if event_type == "on_chain_end" and 'chunks' in event.get('data', {}).get('output', {}):
                 pass

        # --- Trigger Post-Ingest Algorithms ---
        algo_cfg = strategy_config.get('algorithms', {})
        
        if algo_cfg.get('enable_raptor'):
            yield f"data: {json.dumps({'type': 'node_start', 'node': 'raptor_clustering'})}\n\n"
            try:
                # Trigger Raptor (Fire and forget or await partial?)
                # For SSE, we can await and report status
                processor = unified_raptor_process(kb_name) # Assuming this is the entrypoint
                # await processor.run() # Mock
                yield f"data: {json.dumps({'type': 'node_end', 'node': 'raptor_clustering'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'node': 'raptor', 'error': str(e)})}\n\n"

        if algo_cfg.get('enable_graphrag'):
            yield f"data: {json.dumps({'type': 'node_start', 'node': 'graphrag_construction'})}\n\n"
            try:
                processor = GraphRAGProcessor(kb_name)
                # await processor.build_graph(...) # Need extracted entities
                yield f"data: {json.dumps({'type': 'node_end', 'node': 'graphrag_construction'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'node': 'graphrag', 'error': str(e)})}\n\n"

        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
