from typing import Dict, List
import time
from core.state import RAGState, RetrievedChunk, Source
from core.llm.gateway import LLMGateway

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

    gw = LLMGateway()
    t0 = time.perf_counter()
    llm_answer = await gw.chat(prompt=query, context=context)
    answer = llm_answer or f"You asked: {query}\n\nContext length: {len(context)}"
    dur = int((time.perf_counter() - t0) * 1000)
    return {"context": context, "answer": answer, "sources": sources, "step": "generation", "metrics": {"generate": {"duration_ms": dur, "context_len": len(context)}}}
