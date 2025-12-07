import json

from core.llm.gateway import LLMGateway
from core.state import RetrievalState


class QueryPreProcessor:
    def __init__(self):
        # LLM 从 DB 配置加载，避免硬编码
        self.gateway = None

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state["input_query"]
        cfg = state.get("strategy_config") or {}
        provider = cfg.get("llm_provider")
        model = cfg.get("llm_model")
        self.gateway = LLMGateway(provider=provider, model=model)
        # 注入降级链：当主模型不可用时尝试 fallback 列表
        self.gateway.fallback_models = cfg.get("fallback_llm_models") or []

        # 1. Intent Classification & Rewriting
        prompt = f"""
        Analyze the user query.
        1. Detect intent: "factual", "table_query", "summary".
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

        try:
            resp = await self.gateway.chat(prompt)
            # Basic JSON extraction
            start = resp.find("{")
            end = resp.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(resp[start:end])
                state["intent"] = {"type": data.get("intent"), "filters": data.get("filters", {})}
                state["preprocessed_queries"] = [data.get("rewritten_query", query)]
            else:
                state["intent"] = {"type": "factual"}
                state["preprocessed_queries"] = [query]
        except Exception:
            # Fallback
            state["intent"] = {"type": "factual"}
            state["preprocessed_queries"] = [query]

        # TODO: Query Decomposition for complex queries if needed

        return state
