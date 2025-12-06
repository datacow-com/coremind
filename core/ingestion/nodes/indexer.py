from qdrant_client.models import PointStruct
from core.state import IngestState
from core.storage.vector_store import get_vector_client
from core.storage.keyword_store import get_keyword_client
from core.utils.monitor import ingest_duration

class DualIndexer:
    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='indexer').time():
            cfg = state['strategy_config']
            kb_name = state['kb_name']
            version = state['version']
            
            chunks = state['chunks']
            vectors = state['vectors']
            batch_size = cfg.get('index_batch_size', 500)
            
            # 1. Qdrant Indexing
            if cfg.get('vector_backend', 'auto') != 'disabled':
                collection_name = f"kb_{kb_name}_v{version}"
                vector_client = get_vector_client()
                
                # Ensure collection exists
                dim = cfg.get('embedding_dimensions', 1024)
                quant = cfg.get('enable_quantization', True)
                await vector_client.ensure_collection(collection_name, dim=dim, enable_quantization=quant)
                
                # 分批写入，避免超大批次造成超时
                for i in range(0, len(chunks), batch_size):
                    points = []
                    for chunk, vec in zip(chunks[i : i + batch_size], vectors[i : i + batch_size]):
                        points.append(PointStruct(
                            id=chunk['id'],
                            vector=vec,
                            payload={
                                "content": chunk['content'],
                                "metadata": chunk['metadata'],
                                "doc_id": chunk['doc_id'],
                                "chunk_index": chunk['chunk_index']
                            }
                        ))
                    if not points:
                        continue
                    try:
                        await vector_client.upsert(collection_name, points)
                        if 'progress' in state:
                            done = state['progress'].get('indexed_vector', 0) + len(points)
                            state['progress']['indexed_vector'] = done
                    except Exception as e:
                        state['error_log'].append({
                            'stage': 'indexer',
                            'backend': 'vector',
                            'batch_start': i,
                            'error': str(e)
                        })
                        # 不中断其他后端，继续执行 ES
            
            # 2. Elasticsearch Indexing
            if cfg.get('keyword_backend', 'elasticsearch') == 'elasticsearch':
                index_name = f"kb_{kb_name}_docs"
                keyword_client = get_keyword_client()
                
                await keyword_client.ensure_index(index_name)
                
                for i in range(0, len(chunks), batch_size):
                    es_docs = []
                    for chunk in chunks[i : i + batch_size]:
                        es_docs.append({
                            "id": chunk['id'],
                            "content": chunk['content'],
                            "metadata": chunk['metadata'],
                            "doc_id": chunk['doc_id'],
                            "chunk_index": chunk['chunk_index']
                        })
                    if not es_docs:
                        continue
                    try:
                        await keyword_client.bulk_upsert(index_name, es_docs)
                        if 'progress' in state:
                            done = state['progress'].get('indexed_keyword', 0) + len(es_docs)
                            state['progress']['indexed_keyword'] = done
                    except Exception as e:
                        state['error_log'].append({
                            'stage': 'indexer',
                            'backend': 'keyword',
                            'batch_start': i,
                            'error': str(e)
                        })
            
            state['processing_stage'] = 'finalize'
            return state

