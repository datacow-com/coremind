# OmniRAG 内核与遗留模块审计报告

## 1. 存储层 (Storage)
- **状态**: 统一完成。
- **详情**: 
  - `core/storage/index_router.py` 现已成为唯一的写入和检索入口。
  - `core/storage/vector_store.py` 和 `core/storage/keyword_store.py` 封装了新客户端，并提供了 `legacy_add` / `legacy_search` 接口兼容旧代码。
  - `MilvusStore` 和 `LocalIndex` 作为回退路径保留，无逻辑冗余。

## 2. 摄取层 (Ingestion)
- **状态**: 双重实现已解决 (Wrapper模式)。
- **详情**:
  - 遗留模块 (`markdown_ingest.py`, `docx_ingest.py`, etc.) 已更新，不再包含独立的 Embedding/Indexing 逻辑，全部通过 `index_router.add` 路由到新存储。
  - `core/pipeline/builder.py` 实现了智能路由：PDF/图片默认走新 LangGraph (`core/ingestion/graph.py`)，其他格式走遗留 Wrapper 并在底层汇聚。
  - `core/ingestion/graph_ingest.py` (旧 PDF 图) 已标记为 Deprecated，逻辑已迁移至 `core/ingestion/nodes/parser`。

## 3. 检索层 (Retrieval)
- **状态**: 新旧共存，平滑切换。
- **详情**:
  - 新内核 `core/retrieval/graph.py` 实现了完整的 RAG 流程 (RRF, Rerank, Intent)。
  - `server/routes.py` 中的 Chat 接口已更新，根据 `kb_config.use_new_pipeline` 标志位动态切换流量，未强制切断旧逻辑。

## 4. 视觉与节点 (Vision & Nodes)
- **状态**: 整合完成。
- **详情**:
  - `core/vision/yolo_detector.py` 和 `layoutlm_parser.py` 的逻辑已整合进 `GpuVisionParser` 作为本地 Provider 选项。
  - `SmartChunker` 和 `HybridRetriever` 的单元测试已覆盖核心策略。

## 结论
系统核心链路已无逻辑层面的双重实现风险。遗留文件保留仅作为 API 契约的 Wrapper，底层数据流已完全统一。

