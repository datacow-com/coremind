# CoreMind Global Coding Rules

## 1. Value First Principles

- **Visual Integrity**: 解析 PDF 时，**严禁**直接提取文本。必须优先保证表格、多栏布局的结构还原（参考 RAGFlow）。
- **Traceability**: 所有的检索结果必须保留 `bbox` (坐标) 和 `page_number`，以便前端实现“原文高亮”。
- **Feedback Loop**: 系统必须包含“反思”机制。如果检索结果置信度低，必须触发 fallback (联网或拒答)。

## 2. Technical Commandments

- **Async/Await**: Python 后端 (FastAPI, DB drivers, HTTP calls) 必须全异步。
- **Type Hinting**: 必须使用 Pydantic 和 Python 3.11+ 类型注解。
- **LangGraph Standard**: 业务逻辑必须封装在 `langgraph` 的 Nodes 中，禁止散落在 API 视图函数里。
- **Model Neutrality**: 代码中不得硬编码 `OpenAI`。所有模型调用必须通过 `ModelGateway` 接口。

## 3. Dependency Injection

- 使用 `FastAPI` 的 `Depends` 进行服务注入，保持模块解耦。
