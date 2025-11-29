目的：确保前后端交互的流畅性，让用户看到 Agent 的思考过程。
code
Markdown
# Server-Sent Events (SSE) Protocol

Endpoint: `POST /api/chat/stream`

## Event Types

### 1. `event: metadata`
在对话开始时发送，包含 Trace ID。
```json
{ "trace_id": "uuid-...", "model": "gemini-1.5-pro" }
2. event: thought (Agent Thinking)
用于展示 LangGraph 的中间步骤。
code
JSON
{ 
  "node": "web_search", 
  "status": "running", 
  "description": "Searching Google for 'latest RAG architecture'..." 
}
3. event: citation (High Value)
当定位到具体文档时发送。
code
JSON
{
  "doc_id": "abc-123",
  "doc_name": "Q3_Financial_Report.pdf",
  "page": 4,
  "bbox": [100, 200, 500, 600], // For UI highlighting
  "preview_image_url": "/api/files/preview/abc-123/page/4"
}
4. event: message
实际的 LLM 逐字输出。
code
JSON
{ "content": "根据财报显示，", "finish_reason": null }
code
Code
---

## 🛠️ 如何使用这套文档进行 Vibe Coding？

在开发过程中，请按照以下**Prompt 策略**引导 Gemini 3：

1.  **阶段一：搭建骨架**
    > "Vibe, load `@.vibe/00_meta/tech_stack.md` and `@.vibe/01_architecture/system_topology.md`.
    > Initialize a FastAPI project structure. Create the folder hierarchy for `src/ingestion`, `src/graph`, `src/api`.
    > Ensure `pyproject.toml` includes `langgraph`, `pymupdf`, `milvus-python`."

2.  **阶段二：核心解析器 (High Value)**
    > "We are building the Visual Parser. Read `@.vibe/03_core_innovation/3.1_visual_parser/vision_prompting.md`.
    > Implement `src/ingestion/visual_loader.py`.
    > I need the `_extract_table` method to use Gemini 3 Vision API to convert the image crop to Markdown.
    > Use `asyncio` to handle concurrency if processing multiple pages."

3.  **阶段三：编排逻辑**
    > "Let's build the Brain. Refer to `@.vibe/01_architecture/1.2_langgraph/state_schema.md`.
    > Define the `AgentState` class first.
    > Then, implement the `grade_documents` node in `src/graph/nodes/grader.py`. It should check if `retrieved_docs` are relevant to `original_query`."

## 持续价值与进化 (Continuous Value)

*   **文档即测试**：在后期，可以让 AI 根据 `.vibe/03_core_innovation/` 中的算法描述，自动生成单元测试用例（Test Case），验证代码是否偏离了设计初衷。
*   **新同事 Onboarding**：这套文档不仅给 AI 看，也是人类开发者的最佳入职指南，实现了“人机共阅”。
*   **版本控制**：当系统升级（例如从 MVP 到 V2），只需修改 `.vibe` 下的 Markdown 文件，AI 在下一次 Coding Session 中就会自动适应新架构。
