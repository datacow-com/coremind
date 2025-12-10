"""
Batch Embedder - Embeds document chunks in batches.

Features:
- Configurable batch size
- Async/sync embedder support
- Concurrency control
- Progress tracking
"""

import asyncio
from typing import Any

from core.state import IngestState
from core.embedding.registry import get_embedder
from core.utils.monitor import ingest_duration


class BatchEmbedder:
    """
    Batch embedder with concurrency control.
    
    P1 Fix #4: Added semaphore for concurrent batch control
    """
    
    def __init__(self):
        self._semaphore: asyncio.Semaphore | None = None
    
    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='embedder').time():
            cfg = state['strategy_config']
            model_name = cfg.get('embedding_model', 'BAAI/bge-m3')
            batch_size = cfg.get('embedding_batch_size', 64)
            
            # P1 Fix #4: Concurrency control for embedding batches
            max_concurrent = cfg.get('embedding_concurrency', 3)
            if self._semaphore is None or self._semaphore._value != max_concurrent:
                self._semaphore = asyncio.Semaphore(max_concurrent)
            
            chunks = state['chunks']
            if not chunks:
                state['vectors'] = []
                state['processing_stage'] = 'index'
                return state
            
            texts = [c['content'] for c in chunks]
            
            # Get Embedder (uses cached instance via registry)
            embedder = get_embedder(model_name=model_name)

            # Try to preload/validate model config
            if hasattr(embedder, "_ensure_config"):
                try:
                    await embedder._ensure_config()
                except Exception as e:
                    state['error_log'].append({
                        'stage': 'embedder',
                        'error': f'failed to load embedder config for {model_name}: {e}'
                    })
                    raise
            
            vectors = []
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            # Mini-batch processing with concurrency control
            async def embed_batch(batch_idx: int, batch_texts: list[str]) -> list[list[float]]:
                async with self._semaphore:
                    if asyncio.iscoroutinefunction(embedder.embed_batch):
                        batch_vectors = await embedder.embed_batch(batch_texts)
                    else:
                        batch_vectors = await asyncio.to_thread(embedder.embed_batch, batch_texts)
                    return batch_vectors.tolist()
            
            # Process batches with controlled concurrency
            tasks = []
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i : i + batch_size]
                tasks.append(embed_batch(i // batch_size, batch_texts))
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        state['error_log'].append({
                            'stage': 'embedder',
                            'batch_index': i * batch_size,
                            'error': str(result)
                        })
                        raise result
                    vectors.extend(result)
                    
                    # Update progress
                    if 'progress' in state:
                        state['progress']['completed_chunks'] = min(
                            (i + 1) * batch_size, len(texts)
                        )
                        state['progress']['embedding_progress'] = (i + 1) / total_batches
                        
            except Exception as e:
                state['error_log'].append({
                    'stage': 'embedder',
                    'error': str(e)
                })
                raise
            
            state['vectors'] = vectors
            state['processing_stage'] = 'index'
            return state
