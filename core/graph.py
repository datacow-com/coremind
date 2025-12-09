"""
Unified RAG Graph - V4 Architecture

Pure V4 implementation using RetrievalState.
No legacy compatibility layers - clean architecture.
"""

import os
from typing import Any

from langgraph.graph import END, StateGraph

from core.retrieval.nodes.generator import CitationGenerator

# V4 Retrieval Nodes
from core.retrieval.nodes.preprocessor import QueryPreProcessor
from core.retrieval.nodes.reranker import CrossEncoderReranker
from core.retrieval.nodes.retriever import HybridRetriever
from core.state import RetrievalState

# Web Search
from core.tools.web_search_registry import get_web_search_client

_PostgresSaver: Any | None = None
try:
    from langgraph.checkpoint.postgres import PostgresSaver as _PostgresSaver
except Exception:
    _PostgresSaver = None


# --- V4 Nodes (Pure Implementation) ---


class IntentRouter:
    """
    LLM-driven intent router with keyword fallback.

    Intent types:
    - qa: General question answering
    - web_search: Queries requiring real-time/external information
    - table_query: Queries specifically about tabular data
    - image_query: Queries about images/charts
    - summary: Summarization requests
    """

    # Keyword triggers for fast-path (no LLM needed)
    WEB_TRIGGERS = {
        "最新",
        "今天",
        "实时",
        "新闻",
        "current",
        "latest",
        "today",
        "news",
        "股价",
        "天气",
    }
    TABLE_TRIGGERS = {"表格", "数据", "统计", "table", "data", "chart", "excel", "csv"}
    IMAGE_TRIGGERS = {"图片", "图表", "图像", "image", "picture", "diagram", "photo"}
    SUMMARY_TRIGGERS = {"总结", "概括", "摘要", "summarize", "summary", "overview"}

    def __init__(self):
        self.llm = None

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state.get("input_query", "")
        query_lower = query.lower()
        cfg = state.get("strategy_config", {})

        # Fast-path: keyword matching
        if self._keyword_match(query_lower):
            return state

        # LLM-driven intent classification (if configured)
        use_llm_router = cfg.get("use_llm_router", False)
        if use_llm_router:
            try:
                intent = await self._llm_classify(query, cfg)
                state["intent"] = intent
                return state
            except Exception:
                pass  # Fall through to default

        # Default to QA
        if not state.get("intent"):
            state["intent"] = {"type": "qa"}

        return state

    def _keyword_match(self, query: str) -> dict | None:
        """Fast keyword-based intent matching."""
        if any(t in query for t in self.WEB_TRIGGERS):
            return {"type": "web_search"}
        if any(t in query for t in self.TABLE_TRIGGERS):
            return {"type": "table_query"}
        if any(t in query for t in self.IMAGE_TRIGGERS):
            return {"type": "image_query"}
        if any(t in query for t in self.SUMMARY_TRIGGERS):
            return {"type": "summary"}
        return None

    async def _llm_classify(self, query: str, cfg: dict) -> dict:
        """Use LLM for intent classification."""
        import json

        from core.llm.gateway import LLMGateway

        if not self.llm:
            self.llm = LLMGateway(provider=cfg.get("llm_provider"), model=cfg.get("llm_model"))

        prompt = f"""Classify the user query intent.

Query: {query}

Return JSON with:
- type: one of ["qa", "web_search", "table_query", "image_query", "summary"]
- filters: optional filters like {{"language": "zh"}} or {{"block_type": "table"}}
- confidence: 0.0-1.0

Only return the JSON, no other text.
"""

        resp = await self.llm.chat(prompt)

        # Parse JSON response
        start = resp.find("{")
        end = resp.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(resp[start:end])
            return {
                "type": data.get("type", "qa"),
                "filters": data.get("filters", {}),
                "confidence": data.get("confidence", 0.8),
            }

        return {"type": "qa"}


class WebSearchNode:
    """Executes web search and integrates results."""

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state.get("input_query", "")
        if not query:
            return state

        try:
            client = get_web_search_client()
            if client:
                results = await client.search(query, limit=5)
                web_chunks = []
                for i, result in enumerate(results):
                    web_chunks.append(
                        {
                            "id": f"web_{i}",
                            "content": result.get("snippet", ""),
                            "page_num": 0,
                            "doc_id": result.get("url", ""),
                            "chunk_index": i,
                            "metadata": {
                                "source": "web_search",
                                "url": result.get("url"),
                                "title": result.get("title"),
                            },
                            "score": 1.0 - (i * 0.1),
                            "rerank_score": None,
                        }
                    )
                # Merge with existing results
                existing = state.get("fused_results") or []
                state["fused_results"] = web_chunks + existing
        except Exception:
            pass

        return state


class HallucinationChecker:
    """
    LLM-based hallucination detection.

    Compares generated answer claims against source documents
    to identify unsupported assertions.
    """

    def __init__(self):
        self.llm = None

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        answer = state.get("final_answer", "")
        sources = state.get("reranked_results", [])
        cfg = state.get("strategy_config", {})

        # Skip if no answer or sources
        if not answer or not sources:
            return state

        # Skip if hallucination check is disabled
        if not cfg.get("enable_hallucination_check", False):
            return state

        try:
            result = await self._check_hallucination(answer, sources, cfg)
            state["hallucination_check"] = result

            # If high hallucination detected, add warning
            if result.get("score", 0) > cfg.get("hallucination_threshold", 0.5):
                state["final_answer"] = f"⚠️ 警告：回答可能包含不确定信息\n\n{answer}"
        except Exception:
            pass

        return state

    async def _check_hallucination(self, answer: str, sources: list, cfg: dict) -> dict:
        """Use LLM to verify answer against sources."""
        import json

        from core.llm.gateway import LLMGateway

        if not self.llm:
            self.llm = LLMGateway(provider=cfg.get("llm_provider"), model=cfg.get("llm_model"))

        # Build source context
        source_text = "\n\n".join(
            [f"[{i}] {s.get('content', '')[:500]}" for i, s in enumerate(sources[:5])]
        )

        prompt = f"""Verify if the answer is fully supported by the sources.

Answer:
{answer[:1000]}

Sources:
{source_text}

Return JSON with:
- score: 0.0 (fully supported) to 1.0 (completely unsupported)
- unsupported_claims: list of claims not found in sources
- confidence: your confidence in this assessment (0.0-1.0)

Only return the JSON.
"""

        resp = await self.llm.chat(prompt)

        # Parse JSON response
        start = resp.find("{")
        end = resp.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(resp[start:end])

        return {"score": 0.0, "unsupported_claims": [], "confidence": 0.5}


def create_graph():
    """
    Creates the V4 RAG graph.

    Architecture:
    router -> preprocess -> retrieve -> rerank -> check_relevance -> generate -> hallucination -> END
                                                        |
                                                        v (if web_search_needed)
                                                    web_search
    """
    graph = StateGraph(RetrievalState)

    # Instantiate nodes
    router = IntentRouter()
    preprocessor = QueryPreProcessor()
    retriever = HybridRetriever()
    reranker = CrossEncoderReranker()
    generator = CitationGenerator()
    web_search = WebSearchNode()
    hallucination_checker = HallucinationChecker()

    # Register nodes
    graph.add_node("router", router)
    graph.add_node("preprocess", preprocessor)
    graph.add_node("retrieve", retriever)
    graph.add_node("rerank", reranker)
    graph.add_node("generate", generator)
    graph.add_node("web_search", web_search)
    graph.add_node("hallucination", hallucination_checker)

    # Entry point
    graph.set_entry_point("router")

    # Routing logic
    def intent_router(state: RetrievalState) -> str:
        intent = state.get("intent", {})
        intent_type = intent.get("type", "qa") if isinstance(intent, dict) else "qa"
        if intent_type == "web_search":
            return "web_search"
        return "preprocess"

    graph.add_conditional_edges("router", intent_router)

    # Web search path
    graph.add_edge("web_search", "generate")

    # Main retrieval path
    graph.add_edge("preprocess", "retrieve")
    graph.add_edge("retrieve", "rerank")

    def relevance_router(state: RetrievalState) -> str:
        # If not relevant after reranking, try web search
        if not state.get("is_relevant", True):
            loop_count = state.get("loop_count", 0)
            if loop_count < 1:
                return "web_search"
        return "generate"

    graph.add_conditional_edges("rerank", relevance_router)
    graph.add_edge("generate", "hallucination")
    graph.add_edge("hallucination", END)

    # Checkpointer setup
    checkpointer = None
    if _PostgresSaver is not None:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            try:
                checkpointer = _PostgresSaver.from_conn_string(db_url)
            except Exception:
                checkpointer = None

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


# Backward compatibility alias
create_legacy_graph = create_graph
