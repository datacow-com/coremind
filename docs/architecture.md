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