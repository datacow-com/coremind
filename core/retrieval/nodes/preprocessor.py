import json
from core.state import RetrievalState
from core.llm.gateway import LLMGateway

class QueryPreProcessor:
    def __init__(self):
        self.gateway = LLMGateway()

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state['input_query']
        
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
            start = resp.find('{')
            end = resp.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(resp[start:end])
                state['intent'] = {"type": data.get("intent"), "filters": data.get("filters", {})}
                state['preprocessed_queries'] = [data.get("rewritten_query", query)]
            else:
                state['intent'] = {"type": "factual"}
                state['preprocessed_queries'] = [query]
        except Exception:
            # Fallback
            state['intent'] = {"type": "factual"}
            state['preprocessed_queries'] = [query]
            
        # TODO: Query Decomposition for complex queries if needed
        
        return state

