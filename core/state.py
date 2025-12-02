from typing import Any

from typing_extensions import TypedDict


class ProcessedChunk(TypedDict):
    id: str
    content: str
    page_num: int
    doc_id: str
    chunk_index: int
    metadata: dict[str, Any]


class RetrievedChunk(ProcessedChunk):
    score: float
    rerank_score: float | None


class Source(TypedDict):
    chunk_id: str | None
    content: str | None
    score: float | None
    document_name: str | None
    page_number: int | None


class RAGState(TypedDict, total=False):
    query: str
    messages: list[dict[str, Any]]
    intent: str | None
    documents: list[dict[str, Any]]
    chunks: list[ProcessedChunk]
    vectors: list[list[float]]
    retrieved_chunks: list[RetrievedChunk]
    scores: list[float]
    context: str
    answer: str
    sources: list[Source]
    web_results: list[dict[str, Any]]
    web_search_needed: bool
    relevance_score: float
    hallucination_detected: bool
    hallucination_score: float
    steps_taken: list[str]
    step: str
    error: str | None
    metadata: dict[str, Any]
