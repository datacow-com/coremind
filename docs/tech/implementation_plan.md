# OmniRAG 生产级工程实现计划

## 1. 核心目标
构建面向 100TB 规模、多模态（文档+图片）、策略动态可配的 RAG 系统。基于 `system-design.md` 和 `basic-design.md`，落地 **State as Config**（策略即状态）与 **End-to-End Visibility**（端到端可视化）。

## 2. 任务分解 (WBS)

### 阶段一：基础设施与状态定义 (Infrastructure & State)
- [ ] **State Schema 定义 (`core/state.py`)**
    - 实现 `StrategyConfig` (TypedDict/Pydantic)：包含 OCR 引擎、分块策略、Embedding 模型、索引后端等字段。
    - 实现 `IngestState`：包含 `task_id`, `processing_stage`, `parsed_blocks`, `chunks`, `error_log` 等。
    - 实现 `RetrievalState`：包含 `input_query`, `intent`, `retrieved_docs`, `citations` 等。
- [ ] **基础组件封装 (`core/storage/`)**
    - 封装 `ObjectStorage` (MinIO/OSS)：统一流式读写接口 `open(path, mode)`。
    - 封装 `QdrantClient` & `ElasticsearchClient`：支持批量写入、连接池管理、自动创建 Collection/Index。
    - 实现 `PostgresSaver`：用于 LangGraph 的 Checkpointer，支持断点续传。
- [ ] **可观测性基座 (`core/utils/monitor.py`)**
    - 配置 OpenTelemetry SDK：Trace 导出到 Jaeger/Tempo。
    - 定义 Prometheus Metrics：`ingest_duration_seconds`, `job_failure_total`, `retrieval_latency_ms`。

### 阶段二：Ingestion Pipeline 实现 (LangGraph)
- [ ] **LoaderNode (`core/ingestion/nodes/loader.py`)**
    - 实现流式解压 (ZIP/TAR) 与大文件 (PDF) Lazy 加载。
    - 集成 `file_type` 检测。
- [ ] **RouterNode (`core/ingestion/nodes/router.py`)**
    - 实现条件路由逻辑：基于 `force_ocr` 或文件类型 (图片/扫描件) 路由至 GPU Parser。
- [ ] **Parsers (`core/ingestion/nodes/parser/`)**
    - `CpuTextParser`: 基于 PyMuPDF/Unstructured 提取文本与基础表格。
    - `GpuVisionParser`: 实现 Provider 工厂模式 (DeepSeek, Qwen-VL, VolcEngine)；实现速率限制与重试。
- [ ] **Smart Chunker (`core/ingestion/nodes/chunker.py`)**
    - 实现策略分块：Fixed, Semantic (Markdown header), Layout-Aware (基于 Parser 结果)。
- [ ] **Batch Embedder (`core/ingestion/nodes/embedder.py`)**
    - 实现微批次处理 (Mini-batching)；集成 `Infinity` 或本地模型；实现本地 LRU 缓存。
- [ ] **Dual Indexer (`core/ingestion/nodes/indexer.py`)**
    - 实现 Qdrant (Vector) + ES (Keyword) 双写；支持 Metadata 注入 (bbox, page, quality)。
- [ ] **Graph 编排 (`core/ingestion/graph.py`)**
    - 组装 StateGraph，配置 Conditional Edges (Router, Retry) 和 Checkpointer。

### 阶段三：Retrieval & QA 实现 (LangGraph)
- [ ] **Query Preprocessor (`core/retrieval/nodes/preprocessor.py`)**
    - 调用 LLM 进行 Intent 识别、Query Rewrite 和 Decomposition。
- [ ] **Hybrid Retriever (`core/retrieval/nodes/retriever.py`)**
    - 并发查询 Qdrant & ES；实现 RRF 融合算法；支持动态 Filter (基于 Intent)。
- [ ] **Reranker (`core/retrieval/nodes/reranker.py`)**
    - 集成 Cross-Encoder (BGE-Reranker)；实现 Score 截断。
- [ ] **Citation Generator (`core/retrieval/nodes/generator.py`)**
    - 实现 System Prompt 模板 (要求 `<cite>` 格式)；解析 LLM 输出为结构化 Citations (含 bbox/page)。
- [ ] **QA Graph 编排 (`core/retrieval/graph.py`)**
    - 组装 Retrieval Graph，实现 Loop 机制 (Relevance Check -> Rewrite -> Retry)。

### 阶段四：API 与 可视化管控 (Bridge)
- [ ] **API 接口 (`server/api/`)**
    - `POST /ingest/run`: 启动 Ingest Graph，接收 `StrategyConfig`。
    - `GET /ingest/events`: SSE 接口，推送 Graph 状态变更 (Node Start/End, Progress)。
    - `POST /chat`: 启动 Retrieval Graph，支持流式输出 Answer 和 Citations。
- [ ] **前端策略配置 (`frontend/src/components/Strategy/`)**
    - 表单组件：OCR 引擎选择、Chunk 大小滑块、Embedding 模型选择、索引后端开关。
- [ ] **进度可视化 (`frontend/src/components/Monitor/`)**
    - 实时流水线视图：显示当前运行 Node、耗时、错误日志；支持“重试”按钮 (API 触发 Resume)。

### 阶段五：测试与交付
- [ ] **E2E 测试脚本 (`scripts/e2e_full.py`)**
    - 模拟完整流程：上传 PDF -> 配置策略 -> 等待 Index 完成 -> 发起 Chat -> 验证 Citation。
- [ ] **部署配置 (`docker-compose.yml`)**
    - 添加服务：MinIO, Qdrant, Elasticsearch, Redis, Infinity (Embedding Server)。
    - 环境变量模板 `.env.example` 更新。

## 3. 质量与追踪
- **代码质量**: Pydantic 做数据校验，Type Hints 全覆盖。
- **单元测试**: 核心 Node (Chunker, Retriever) 覆盖率 > 80%。
- **集成测试**: 每日构建运行 E2E 脚本。
- **文档**: 更新 API 文档与部署手册。

