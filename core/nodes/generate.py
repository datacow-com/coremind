from typing import Dict, List
from core.state import RAGState, RetrievedChunk, Source

async def generate(state: RAGState) -> Dict:
    query = state.get("query", "")
    chunks: List[RetrievedChunk] = state.get("retrieved_chunks", [])
    context = "\n\n".join([c.get("content", "") for c in chunks])

    sources: List[Source] = []
    for c in chunks:
        src: Source = {
            "chunk_id": c.get("id"),
            "content": c.get("content"),
            "score": c.get("score"),
            "document_name": c.get("doc_id"),
            "page_number": c.get("page_num"),
        }
        sources.append(src)

    answer = f"You asked: {query}\n\nContext length: {len(context)}"
    return {"context": context, "answer": answer, "sources": sources, "step": "generation"}
