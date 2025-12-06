import os
import zipfile
import tarfile
import aiofiles
from core.state import IngestState
from core.storage.blob_store import get_blob_store
from core.utils.monitor import ingest_duration, ingest_requests

class LoaderNode:
    async def __call__(self, state: IngestState) -> IngestState:
        """
        Load file content from blob storage or local path.
        Handle archive expansion or lazy loading for large files.
        """
        with ingest_duration.labels(stage='loader').time():
            try:
                file_path = state['file_path']
                file_type = state['file_type']
                blob_store = get_blob_store()
                
                # Update stage
                state['processing_stage'] = 'parse'
                
                # 1. Archive handling (Zip/Tar) -> In a real system, this might dispatch sub-jobs
                # For MVP, we skip complex recursive unarchiving or assume simple files for now.
                # Future: if zip, yield new states for subgraph.
                
                # 2. Large PDF Lazy Load check
                # If PDF > 100MB, we might not load raw_content entirely into memory here,
                # but let Parser handle stream or download to temp.
                # For simplicity, we read content if it's reasonable size or required.
                
                # Check size if possible (blob store head/stat)
                # For now, just read.
                
                if not await blob_store.exists(file_path):
                     raise FileNotFoundError(f"File {file_path} not found in blob store")

                # Read content
                content = await blob_store.get(file_path)
                state['raw_content'] = content
                
                ingest_requests.labels(stage='loader', status='success').inc()
                return state
                
            except Exception as e:
                state['error_log'].append({
                    'stage': 'loader',
                    'error': str(e)
                })
                ingest_requests.labels(stage='loader', status='error').inc()
                # Depending on graph design, might return state to route to error_handler
                return state

