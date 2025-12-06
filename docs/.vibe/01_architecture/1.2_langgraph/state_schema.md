# LangGraph State Definition

## Core State: `AgentState`

该状态在整个 Graph 的生命周期中传递。

```python
from typing import TypedDict, List, Annotated, Optional
import operator

class AgentState(TypedDict):
    # 1. Conversation History (Standard)
    messages: Annotated[List[BaseMessage], operator.add]

    # 2. Query Understanding
    original_query: str
    rewritten_query: Optional[str] # Optimized for vector search
    intent: str # 'fact_qa', 'summary', 'web_search', 'chitchat'

    # 3. Retrieval Context
    retrieved_docs: List[DocumentChunk] # From Milvus
    web_results: List[WebSearchResult] # From Tavily/Serper

    # 4. Self-Reflection Metrics
    relevance_score: float # 0.0 to 1.0 (from Grader Node)
    hallucination_detected: bool

    # 5. Execution Metadata
    steps_taken: List[str] # e.g. ["router", "retrieve", "grade(fail)", "web_search"]
    current_retry_count: int

    State Transitions (Edges)
        router_node: Based on intent, route to rag_flow or web_flow.
        grader_node:
        If relevance_score > 0.7 -> generate_node.
        If relevance_score < 0.7 -> web_search_node.
```
