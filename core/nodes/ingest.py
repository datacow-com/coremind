from typing import Dict, List
from core.state import RAGState, ProcessedChunk

async def ingest(state: RAGState) -> Dict:
    chunks: List[ProcessedChunk] = []
    return {"chunks": chunks, "step": "ingestion"}
