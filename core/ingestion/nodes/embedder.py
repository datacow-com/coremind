import asyncio
from core.state import IngestState
from core.embedding.registry import get_embedder
from core.utils.monitor import ingest_duration

class BatchEmbedder:
    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='embedder').time():
            cfg = state['strategy_config']
            model_name = cfg.get('embedding_model', 'BAAI/bge-m3')
            batch_size = cfg.get('embedding_batch_size', 64)
            
            chunks = state['chunks']
            texts = [c['content'] for c in chunks]
            
            # Get Embedder (Wrapper around Provider)
            # We assume get_embedder returns an object with embed_batch(texts) -> np.ndarray
            embedder = get_embedder(model_name=model_name)

            # 尝试预加载/校验模型配置，便于与 UI/DB 注册对齐
            if hasattr(embedder, "_ensure_config"):
                try:
                    await embedder._ensure_config()  # type: ignore
                except Exception as e:
                    state['error_log'].append({
                        'stage': 'embedder',
                        'error': f'failed to load embedder config for {model_name}: {e}'
                    })
                    raise
            
            vectors = []
            
            # Mini-batch processing
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                try:
                    # Assume embed_batch is async or wrapped in asyncio.to_thread inside
                    # If it is sync (like current simple_embedder), wrap it.
                    if asyncio.iscoroutinefunction(embedder.embed_batch):
                        batch_vectors = await embedder.embed_batch(batch_texts)
                    else:
                        batch_vectors = await asyncio.to_thread(embedder.embed_batch, batch_texts)
                    
                    # Convert numpy to list
                    vectors.extend(batch_vectors.tolist())
                    
                    # Update progress
                    if 'progress' in state:
                        state['progress']['completed_chunks'] = i + len(batch_texts)
                        
                except Exception as e:
                    state['error_log'].append({
                        'stage': 'embedder',
                        'batch_index': i,
                        'error': str(e)
                    })
                    raise e
            
            state['vectors'] = vectors
            state['processing_stage'] = 'index'
            return state

