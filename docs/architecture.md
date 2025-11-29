# OmniRAG Architecture (LangGraph Centric)

## 1. The Brain: `MasterGraph` (Orchestration)
系统不分层，而是分“节点” (Nodes)。
- **Router Node**: 基于用户 Query 进行意图分类 (Chat / RAG / Web / ComplexTask)。
- **RAG Node**: 执行检索增强生成。
- **WebSearch Node**: 执行联网搜索。
- **Grade Node**: (创新点) 对检索回来的文档进行打分，如果分数低，自动回退到 WebSearch。
- **Generate Node**: 最终生成答案。

## 2. The Eyes: `DeepIngestionService` (Unique Value)
*独立于 Graph 运行的 ETL 流水线。*
- **Pipeline**: Upload API -> Queue -> Visual Parser -> Chunker -> Milvus.
- **Output**: 产生高质量的 `Document` 对象，带有丰富的 metadata（如表格的 HTML 源码、图片的描述）。

## 3. The Deployment: LangServe
- 使用 LangServe 将 `MasterGraph` 直接暴露为 REST API。
- 支持 Stream Log，前端可以实时看到 Agent “正在思考”、“正在检索”、“正在阅读图片”。

## 4. Persistence (Memory)
- 使用 `PostgresSaver`。
- 每一个 `thread_id` 对应一个用户的会话历史。系统自动处理历史记录的注入。
 - 已在 `core/graph.py` 集成可选的 PostgresSaver（通过 `DATABASE_URL` 启用），`server/routes.py` 在 `/chat` 传递 `thread_id` 用于持久化线程上下文。

## 5. 目录结构与职责

```
OmniRAG/
├── core/                  # 业务内核（LangGraph 与能力层）
│   ├── graph.py           # StateGraph 编排（入口）
│   ├── state.py           # RAG 状态（TypedDict）
│   ├── nodes/             # 工作流节点（async）
│   ├── loaders/           # 视觉解析（PDF→PNG、表格裁切、Vision/OCR）
│   ├── embedding/         # 嵌入提供者（OpenAI/ST/回退）
│   ├── storage/           # 索引与路由（Milvus 优先、本地回退、BM25）
│   ├── reranker/          # 重排（CrossEncoder，失败回退词重叠）
│   └── llm/               # LLM 网关（OpenAI/Gemini/OpenRouter）
├── server/                # 服务层（HTTP 边界）
│   ├── main.py            # FastAPI + LangServe 挂载
│   ├── routes.py          # REST API（上传/状态/下载/模型网关）
│   ├── schemas.py         # API 契约（Pydantic）
│   └── auth.py            # JWT 鉴权
├── frontend/              # 前端（Chat/Settings/Documents/VectorStore）
├── docs/                  # PRD/架构/产品与项目文档
├── tests/                 # 解析/检索/路由/鉴权测试
└── data/                  # 运行数据（uploads/ 与 config/providers.json）
```

说明：
- `core` 专注能力实现与 LangGraph 编排，不感知 HTTP；所有节点 `async def` 遵循项目规则
- `server` 专注服务暴露、鉴权与契约；通过 LangServe 暴露 Graph
- `backend/` 为历史脚手架目录，已从脚本与工作区移除；其中的可用能力（如 PostgresSaver 集成）将按计划迁移至 `core/storage` 或 `server/`（详见 Roadmap）
