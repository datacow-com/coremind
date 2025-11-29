# OmniRAG Vibe Coding Rules (LangGraph Edition)

## 1. Architectural Backbone: LangGraph
- **Strict Adherence**: 所有业务逻辑流程（工作流、Agent 思考、工具调用）**必须**使用 `langgraph` 构建。
- **No Custom Loops**: 严禁手写 `while` 循环或自定义的状态机。一切状态流转通过 `StateGraph`、`nodes` 和 `edges` 定义。
- **Standard Interface**: 所有组件必须兼容 `langchain_core` 标准（如 `BaseRetriever`, `BaseTool`）。

## 2. The Core Innovation: Visual Ingestion
- **Custom Loader**: 在数据处理层，**严禁**使用 `Unstructured` 或 `PyPDF` 的默认设置。
- **Mandate**: 必须实现一个 `VisualPDFLoader`，流程是：PDF -> Image -> VLM (Gemini/GPT-4o) -> Structured Markdown。这是本系统的**核心竞争力**。

## 3. Technology Stack
- **Orchestration**: LangGraph, LangChain.
- **Backend API**: FastAPI (using `langserve` for graph deployment).
- **Database**: 
  - **Vector**: Milvus.
  - **Checkpointer**: Postgres (via `langgraph-checkpoint-postgres`) 用于持久化 Agent 记忆。
- **LLM**: Gemini 3 (Primary Brain).

## 4. Coding Style
- **Type Safety**: 使用 `TypedDict` 定义 LangGraph 的 State。
- **Async**: 所有 Node 函数必须是 `async def`。