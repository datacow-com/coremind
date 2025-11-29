# Development Plan

## Phase 1: The Unique Parser (High Value First)
**Goal**: Build `src/ingestion/visual_loader.py`.
1. Implement `render_page_to_image`.
2. Implement `extract_table_with_vlm` using Gemini 3.
3. Combine them into a Loader that outputs LangChain `Document` objects.
4. Test with a complex financial report PDF.

## Phase 2: The Graph Skeleton (LangGraph)
**Goal**: Build `src/graph/workflow.py`.
1. Define `AgentState`.
2. Create basic Nodes: `retrieve`, `generate`.
3. Build the graph: `workflow.add_node`, `workflow.add_edge`.
4. Serve with LangServe (`server.py`).

## Phase 3: Adaptive Intelligence
**Goal**: Add the "Smart" Nodes.
1. Implement `grade_documents` node (Relevance Check).
2. Implement `web_search` node (Tavily/Serper).
3. Add Conditional Edges (`decide_to_generate`).

## Phase 4: Integration
**Goal**: Connect Phase 1 data to Phase 2 retrieval.
1. Setup Milvus with `LangChain` vectorstore wrapper.
2. Run the ingestion pipeline to populate Milvus.
3. Connect the Graph's retriever to Milvus.