"""
Query Preprocessor - Intent classification and query rewriting.

Features:
- Intent classification (factual, table_query, summary, web_search)
- Language detection
- Query rewriting for better search
- Configurable prompts (P2 Fix #8)
"""

import json
from typing import Any

from core.llm.gateway import LLMGateway
from core.state import RetrievalState


# Default intent classification prompt
DEFAULT_INTENT_PROMPT = """
Analyze the user query.
1. Detect intent: "factual", "table_query", "summary", "web_search", "image_query".
2. Detect language: "zh", "en".
3. Rewrite the query to be search-friendly (remove polite words, fix typos, resolve coreferences if history provided).

Return JSON:
{{
    "intent": "factual",
    "language": "zh",
    "rewritten_query": "...",
    "filters": {{ "block_type": "table" }} // only if intent is table_query
}}

Query: {query}
"""


class QueryPreProcessor:
    """
    Query preprocessor with intent classification and rewriting.
    
    P1 Fix #7: Uses cached LLMGateway instance
    P2 Fix #8: Configurable intent prompt
    """
    
    # P1 Fix #7: Class-level gateway cache
    _gateway_cache: dict[str, LLMGateway] = {}
    
    def __init__(self):
        pass

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state["input_query"]
        cfg = state.get("strategy_config") or {}
        provider = cfg.get("llm_provider")
        model = cfg.get("llm_model")
        
        # P1 Fix #7: Reuse cached gateway
        cache_key = f"{provider}:{model}"
        if cache_key not in QueryPreProcessor._gateway_cache:
            gateway = LLMGateway(provider=provider, model=model)
            QueryPreProcessor._gateway_cache[cache_key] = gateway
        
        gateway = QueryPreProcessor._gateway_cache[cache_key]
        gateway.fallback_models = cfg.get("fallback_llm_models") or []

        # P2 Fix #8: Use configurable prompt template
        prompt_template = cfg.get("intent_prompt_template") or DEFAULT_INTENT_PROMPT
        prompt = prompt_template.format(query=query)

        try:
            resp = await gateway.chat(prompt)
            # Basic JSON extraction
            start = resp.find("{")
            end = resp.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(resp[start:end])
                state["intent"] = {
                    "type": data.get("intent", "factual"),
                    "filters": data.get("filters", {}),
                    "language": data.get("language"),
                }
                state["preprocessed_queries"] = [data.get("rewritten_query", query)]
            else:
                state["intent"] = {"type": "factual"}
                state["preprocessed_queries"] = [query]
        except Exception:
            # Fallback
            state["intent"] = {"type": "factual"}
            state["preprocessed_queries"] = [query]

        return state


def clear_preprocessor_cache() -> None:
    """Clear the gateway cache. Useful for testing."""
    QueryPreProcessor._gateway_cache.clear()
