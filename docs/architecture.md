# OmniRAG 系统架构设计

> **版本**: v2.0 | **最后更新**: 2025-12-08
> **设计参照**: `docs/tech/system-design.md` (Single Source of Truth)

---

## 1. 架构总览

### 1.1 设计原则

| 原则 | 描述 | 实现策略 |
|:-----|:-----|:---------|
| **State as Config** | 所有运行时参数通过 LangGraph State 传递 | UI 动态注入 `strategy_config` |
| **Multi-Modal First** | 统一处理 PDF/Office/图片/HTML | 智能路由 CPU/GPU Parser |
| **Production-Grade** | 100TB 数据，P95 < 1.5s | 向量压缩、热冷分层、连接池 |
| **Observable** | 全链路追踪 | OTel + Prometheus + SSE 推送 |
| **Configurable** | UI 端可配置所有策略 | DB 驱动的 Provider/Model 配置 |

### 1.2 核心性能约束

```
┌────────────────────────────────────────────────────────┐
│                    Performance SLA                      │
├─────────────────────┬──────────────────────────────────┤
│ 向量检索 P95        │ < 500ms                          │
│ 端到端问答 P95      │ < 1.5s                           │
│ 文档摄取吞吐        │ 10 docs/min (单节点)             │
│ 系统可用性          │ ≥ 99.9%                          │
│ 模型加载            │ Singleton，首次加载后复用         │
└─────────────────────┴──────────────────────────────────┘
```

### 1.3 业务背景与多 Channel 架构

#### 1.3.1 数据规模

```
┌─────────────────────────────────────────────────────────────────────┐
│                      数据规模: 100TB ~ 500TB                         │
│                                                                      │
│   总数据量 100TB ~ 500TB → 分布在多个业务区域 (Channel)              │
│                                                                      │
│   每个 Channel:                                                      │
│   - 数据量: 10TB ~ 100TB                                             │
│   - 文档数: 1000万 ~ 1亿                                             │
│   - 知识库数: 5 ~ 50                                                 │
│   - 活跃用户: 100 ~ 10000                                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 1.3.2 业务隔离架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              MULTI-CHANNEL ARCHITECTURE                       │
│                                                                               │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │    CHANNEL A        │  │    CHANNEL B        │  │    CHANNEL C        │  │
│  │    (法律合规)       │  │    (产品研发)       │  │    (客户服务)       │  │
│  │                     │  │                     │  │                     │  │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │
│  │  │ KB: 法规库    │  │  │  │ KB: 技术文档  │  │  │  │ KB: FAQ 库    │  │  │
│  │  │ KB: 判例库    │  │  │  │ KB: 专利库    │  │  │  │ KB: 工单库    │  │  │
│  │  │ KB: 政策库    │  │  │  │ KB: 设计规范  │  │  │  │ KB: 产品说明  │  │  │
│  │  └───────────────┘  │  │  └───────────────┘  │  │  └───────────────┘  │  │
│  │                     │  │                     │  │                     │  │
│  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │  ┌───────────────┐  │  │
│  │  │  Chat 1       │  │  │  │  Chat 1       │  │  │  │  Chat 1       │  │  │
│  │  │  Chat 2       │  │  │  │  Chat 2       │  │  │  │  Chat 2       │  │  │
│  │  └───────────────┘  │  │  └───────────────┘  │  │  └───────────────┘  │  │
│  │                     │  │                     │  │                     │  │
│  │  数据完全隔离 🔒    │  │  数据完全隔离 🔒    │  │  数据完全隔离 🔒    │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
│                                                                               │
│  ══════════════════════════════════════════════════════════════════════════  │
│                           SHARED INFRASTRUCTURE                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ Qdrant   │  │   ES     │  │ Postgres │  │  MinIO   │  │  Redis   │      │
│  │ (分区)   │  │ (分区)   │  │ (隔离)   │  │ (桶隔离)  │  │ (前缀)   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### 1.3.3 Channel-KB-Chat 三层模型

```
┌────────────────────────────────────────────────────────────────────────┐
│                           CHANNEL (业务区域)                            │
│  - 代表独立的业务部门或业务线                                            │
│  - 拥有独立的数据存储分区                                                │
│  - 拥有独立的权限边界和用户群                                            │
│  - 可配置独立的 LLM/Embedding Provider                                  │
├────────────────────────────────────────────────────────────────────────┤
│                                    │                                    │
│                    ┌───────────────┼───────────────┐                   │
│                    ▼               ▼               ▼                   │
│  ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐│
│  │  KNOWLEDGE BASE (KB) │ │  KNOWLEDGE BASE (KB) │ │  KNOWLEDGE BASE  ││
│  │                      │ │                      │ │                  ││
│  │  独立策略配置:       │ │  独立策略配置:       │ │  独立策略配置:   ││
│  │  - 分块策略          │ │  - 分块策略          │ │  - 分块策略      ││
│  │  - OCR Provider      │ │  - OCR Provider      │ │  - OCR Provider  ││
│  │  - 检索权重          │ │  - 检索权重          │ │  - 检索权重      ││
│  │  - 高级算法          │ │  - 高级算法          │ │  - 高级算法      ││
│  └──────────┬───────────┘ └──────────┬───────────┘ └────────┬─────────┘│
│             │                        │                      │          │
│             └────────────────────────┼──────────────────────┘          │
│                                      ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                         CHAT SESSION                              │  │
│  │  - 可绑定多个 KB (跨 KB 检索)                                      │  │
│  │  - 运行时覆盖参数 (top_k, temperature)                            │  │
│  │  - 对话历史持久化                                                  │  │
│  │  - 支持 A/B 测试                                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

#### 1.3.4 KB 独立配置能力

根据知识库内容的**格式**、**业务性质**、**业务特性**进行差异化配置:

| 业务场景 | 内容格式 | 推荐配置 |
|:---------|:---------|:---------|
| **法律法规** | 结构化 PDF | `chunk_size=800`, `semantic`, `GraphRAG`, 高精度 OCR |
| **技术文档** | Markdown/HTML | `chunk_size=600`, `layout_aware`, 标准检索 |
| **财务报表** | 表格 PDF | `table_first`, 强制 OCR, 专用表格解析 |
| **产品说明** | 图文混合 | `multimodal`, VLM 解析, 图文联合检索 |
| **客服 FAQ** | 短文本 | `chunk_size=256`, 关键词权重高, 快速匹配 |
| **学术论文** | 长文档 | `chunk_size=1200`, RAPTOR 聚类, 引用追踪 |

#### 1.3.5 数据隔离实现

| 存储层 | 隔离策略 | 实现方式 |
|:-------|:---------|:---------|
| **Qdrant** | Collection 分区 | `kb_{channel}_{kb_name}_v{version}` |
| **Elasticsearch** | Index 分区 | `kb_{channel}_{kb_name}_docs` |
| **PostgreSQL** | 行级隔离 | `channel_id` 字段 + RLS Policy |
| **MinIO** | Bucket 隔离 | `channel-{channel_id}/` 前缀 |
| **Redis** | Key 前缀 | `{channel}:{kb}:{key}` |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Chat UI   │  │  Config UI  │  │  Ingest UI  │  │   SDK/API   │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │ SSE/REST       │ REST           │ SSE/REST       │ REST
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            SERVER LAYER                                  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                     FastAPI (server/)                             │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │  │
│  │  │ routes.py│  │ auth.py  │  │schemas.py│  │ api/ingest.py    │  │  │
│  │  └────┬─────┘  └────┬─────┘  └──────────┘  └────────┬─────────┘  │  │
│  └───────┼─────────────┼───────────────────────────────┼────────────┘  │
└──────────┼─────────────┼───────────────────────────────┼────────────────┘
           │             │                               │
           ▼             ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             CORE LAYER                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    LangGraph Pipelines                          │    │
│  │  ┌─────────────────────┐    ┌─────────────────────────────┐    │    │
│  │  │   IngestGraph       │    │      RetrievalGraph         │    │    │
│  │  │ (core/ingestion/)   │    │  (core/graph.py + bridges)  │    │    │
│  │  └─────────┬───────────┘    └──────────────┬──────────────┘    │    │
│  └────────────┼────────────────────────────────┼──────────────────┘    │
│               ▼                                ▼                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    Capability Modules                          │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │    │
│  │  │embedding/│ │reranker/ │ │  llm/    │ │ vision/  │          │    │
│  │  │ registry │ │ registry │ │ gateway  │ │ parsers  │          │    │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │    │
│  └───────┼────────────┼────────────┼────────────┼────────────────┘    │
│          │            │            │            │                      │
│  ┌───────▼────────────▼────────────▼────────────▼────────────────┐    │
│  │                    Model Gateway                               │    │
│  │           (core/model_gateway/config_store.py)                │    │
│  │      DB-driven provider/model configuration                   │    │
│  └────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │   Qdrant     │  │ Elasticsearch│  │  PostgreSQL  │  │MinIO/OSS   │  │
│  │ (Vector)     │  │  (Keyword)   │  │ (Metadata)   │  │  (Blob)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构与职责

```
OmniRAG/
├── core/                      # 业务内核（LangGraph + 能力层）
│   ├── graph.py               # ✅ 统一 RAG Graph（V4 Bridges）
│   ├── state.py               # ✅ 状态定义（IngestState, RetrievalState）
│   │
│   ├── ingestion/             # 摄取管道
│   │   ├── graph.py           # LangGraph 摄取流程编排
│   │   └── nodes/             # 摄取节点（loader, parser, chunker...）
│   │
│   ├── retrieval/             # V4 检索管道
│   │   ├── graph.py           # LangGraph QA 流程编排
│   │   └── nodes/             # 检索节点（preprocessor, retriever, reranker, generator）
│   │
│   ├── algorithms/            # 高级 RAG 算法
│   │   ├── raptor.py          # RAPTOR 聚类摘要
│   │   ├── raptor_light.py    # 轻量版 RAPTOR Graph
│   │   ├── graphrag.py        # GraphRAG 知识图谱
│   │   └── graphrag_deep.py   # 深度 GraphRAG Graph
│   │
│   ├── embedding/             # 向量化服务
│   │   └── registry.py        # 多 Provider 注册（Infinity/OpenAI/Local）
│   │
│   ├── reranker/              # 重排序服务
│   │   ├── registry.py        # 多 Provider 注册
│   │   └── cross_encoder.py   # ✅ Singleton CrossEncoder
│   │
│   ├── llm/                   # LLM 网关
│   │   ├── gateway.py         # 统一调用入口 + 熔断 + 降级
│   │   └── providers/         # OpenAI/DashScope/Anthropic
│   │
│   ├── vision/                # 视觉解析
│   │   ├── layoutlm_parser.py # ✅ LRU缓存 LayoutLM
│   │   ├── yolo_detector.py   # ✅ LRU缓存 YOLO
│   │   └── table.py           # 表格提取
│   │
│   ├── storage/               # 存储抽象层
│   │   ├── vector_store.py    # Qdrant/Milvus 客户端 (Singleton)
│   │   ├── keyword_store.py   # Elasticsearch 客户端 (Singleton)
│   │   ├── blob_store.py      # MinIO/OSS/Local 客户端
│   │   ├── kb_config.py       # 知识库配置管理
│   │   └── index_router.py    # 双写路由
│   │
│   ├── model_gateway/         # DB 驱动的模型配置
│   │   └── config_store.py    # Provider/Model CRUD
│   │
│   ├── pipeline/              # 管道辅助
│   │   ├── registry.py        # 管道注册表
│   │   └── kb_merge.py        # KB 参数合并
│   │
│   └── utils/                 # 工具函数
│       ├── monitor.py         # Prometheus 指标
│       └── trace.py           # OTel 追踪
│
├── server/                    # HTTP 服务层
│   ├── main.py                # FastAPI 入口
│   ├── routes.py              # 业务路由（Chat/Ingest/Config）
│   ├── api/                   # API 子模块
│   │   └── ingest.py          # 摄取 API（SSE 流式）
│   ├── schemas.py             # Pydantic 契约
│   ├── auth.py                # JWT 鉴权
│   ├── config.py              # 服务配置
│   ├── database.py            # SQLAlchemy 引擎
│   ├── base.py                # DeclarativeBase
│   └── models.py              # ORM 模型（Provider/Model/KB）
│
├── frontend/                  # React 前端
│   └── src/
│       ├── pages/             # Chat/Documents/Settings/VectorStore
│       ├── components/        # StrategyConfig/IngestProgress
│       └── hooks/             # useIngestProgress/useChat
│
├── embedded-ui/               # 嵌入式轻量 UI
│
├── docs/                      # 文档
│   └── tech/
│       └── system-design.md   # 详细设计（Source of Truth）
│
├── scripts/                   # 运维脚本
│   └── dev.sh                 # 开发启动脚本
│
└── data/                      # 运行时数据
    ├── uploads/               # 上传文件
    └── config/                # 本地配置
```

---

## 4. LangGraph 管道架构

### 4.1 Ingestion Pipeline

```
                         IngestState
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        ▼                        │
    │  ┌─────────────────────────────────────────┐   │
    │  │              LoaderNode                 │   │
    │  │   - 流式解压 ZIP/TAR                    │   │
    │  │   - 超大 PDF Lazy 加载                  │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │              RouterNode                 │   │
    │  │   - force_ocr → GPU                     │   │
    │  │   - 扫描件检测 → GPU                    │   │
    │  │   - 文本 PDF/DOCX/MD → CPU              │   │
    │  └──────────┬────────────┬─────────────────┘   │
    │             │            │                     │
    │     ┌───────▼───┐  ┌─────▼─────┐              │
    │     │CpuParser │  │GpuVision  │              │
    │     │PyMuPDF   │  │Qwen-VL    │              │
    │     │python-   │  │DeepSeek   │              │
    │     │docx      │  │PaddleOCR  │              │
    │     └─────┬─────┘  └─────┬─────┘              │
    │           │              │                     │
    │           └──────┬───────┘                     │
    │                  ▼                             │
    │  ┌─────────────────────────────────────────┐   │
    │  │          QualityValidator               │   │
    │  │   - 质量评分                            │   │
    │  │   - 语言检测                            │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │            SmartChunker                 │   │
    │  │   - fixed / semantic / layout_aware     │   │
    │  │   - table_first (表格独立成块)          │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │            BatchEmbedder                │   │
    │  │   - Infinity Server / OpenAI            │   │
    │  │   - SHA256 缓存 (LRU 10000)             │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │             DualIndexer                 │   │
    │  │   - Qdrant 向量写入                     │   │
    │  │   - ES 关键词索引                       │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │              Finalizer                  │   │
    │  │   - 更新 KB 元数据                      │   │
    │  │   - 触发 RAPTOR/GraphRAG (可选)         │   │
    │  └─────────────────────────────────────────┘   │
    │                                                │
    └────────────────────────────────────────────────┘
```

### 4.2 Retrieval Pipeline (V4)

```
                        RetrievalState
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        ▼                        │
    │  ┌─────────────────────────────────────────┐   │
    │  │          QueryPreProcessor              │   │
    │  │   - 语言检测                            │   │
    │  │   - Intent 识别                         │   │
    │  │   - Query Rewrite (重试时)              │   │
    │  │   - Query Decomposition (复合问题)      │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │         SemanticCacheChecker            │   │
    │  │   - 语义相似度匹配                      │   │
    │  │   - cache_hit → 直接返回                │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │           HybridRetriever               │   │
    │  │   - 向量检索 (Qdrant)                   │   │
    │  │   - 关键词检索 (ES)                     │   │
    │  │   - RRF 融合 (可配置权重)               │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │         CrossEncoderReranker            │   │
    │  │   - bge-reranker-v2-m3 (Singleton)      │   │
    │  │   - asyncio.to_thread 包装              │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     ▼                          │
    │  ┌─────────────────────────────────────────┐   │
    │  │          RelevanceGrader                │   │
    │  │   - is_relevant 判断                    │   │
    │  │   - loop_count < 2 → 重写重试           │   │
    │  └──────────────────┬──────────────────────┘   │
    │                     │                          │
    │         ┌───────────┴───────────┐             │
    │         ▼                       ▼             │
    │   ┌──────────┐           ┌──────────┐        │
    │   │Rewrite   │           │Generator │        │
    │   │(loop)    │           │Citation  │        │
    │   └────┬─────┘           └────┬─────┘        │
    │        │                      ▼              │
    │        │            ┌─────────────────┐      │
    │        │            │HallucinationGua │      │
    │        │            │- 事实核查       │      │
    │        │            │- 降低置信度     │      │
    │        │            └────────┬────────┘      │
    │        │                     ▼               │
    │        └─────────────────→ END               │
    │                                              │
    └──────────────────────────────────────────────┘
```

---

## 5. 状态设计 (State as Config)

### 5.1 IngestState

```python
class IngestState(TypedDict):
    # 多 Channel 隔离
    channel_id: str             # 业务区域 ID (数据隔离边界)

    # 元数据
    task_id: str
    file_path: str
    file_type: str
    batch_id: str
    kb_name: str
    version: int

    # 策略配置 (UI 注入)
    strategy_config: StrategyConfig  # 分块/OCR/嵌入/索引策略

    # 管道数据
    raw_content: Optional[bytes]
    parsed_blocks: List[Dict]
    chunks: List[Dict]
    vectors: List[List[float]]

    # 状态控制
    processing_stage: Literal["upload", "parse", "chunk", "embed", "index", "finalize"]
    retry_count: int
    error_log: List[Dict]
    progress: Dict[str, Any]
    quality_metrics: Dict[str, float]
```

### 5.2 RetrievalState

```python
class RetrievalState(TypedDict):
    # 多 Channel 隔离
    channel_id: str             # 业务区域 ID (数据隔离边界)
    session_id: str             # Chat Session ID

    # 输入
    query_id: str
    input_query: str
    chat_history: List[Dict]
    kb_names: List[str]         # 可绑定多个 KB (跨 KB 检索)
    user_id: str

    # 策略配置 (UI 注入)
    strategy_config: Dict[str, Any]  # top_k, temperature, rerank_model

    # 中间态
    preprocessed_queries: List[str]
    intent: Dict[str, Any]

    # 检索结果
    vector_results: List[Dict]
    keyword_results: List[Dict]
    fused_results: List[Dict]
    reranked_results: List[Dict]

    # 控制
    is_relevant: bool
    loop_count: int
    cache_hit: bool

    # 输出
    final_answer: str
    citations: List[Dict]
    confidence: float
```

---

## 6. 配置体系 (UI Configurable)

### 6.1 三层配置架构

```
┌────────────────────────────────────────────────────────────┐
│                 Layer 1: System Defaults                   │
│                 (server/config.py)                         │
│  - 环境变量                                                 │
│  - 全局默认参数                                             │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │ 覆盖
┌────────────────────────────────────────────────────────────┐
│                 Layer 2: Channel Config                    │
│                 (Channel.config)                           │
│  - 业务区域级配置                                           │
│  - Provider 绑定                                            │
│  - 安全策略                                                 │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │ 覆盖
┌────────────────────────────────────────────────────────────┐
│                 Layer 3: Knowledge Base Config             │
│                 (KBConfig.config)                          │
│  - 每个 KB 独立配置                                         │
│  - 分块/OCR/检索策略                                        │
│  - UI 可编辑                                                │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │ 覆盖
┌────────────────────────────────────────────────────────────┐
│                 Layer 4: Request-Level Override            │
│                 (strategy_config in State)                 │
│  - 每次请求可覆盖                                           │
│  - Chat Session 配置                                        │
│  - A/B 测试支持                                             │
└────────────────────────────────────────────────────────────┘
```

### 6.2 可配置项列表

| 配置分类 | 配置项 | UI 位置 | 默认值 |
|:---------|:-------|:--------|:-------|
| **OCR** | `ocr_provider` | 知识库设置 | `auto` |
| | `ocr_fallback_chain` | 知识库设置 | `["qwen-vl", "paddle"]` |
| | `force_ocr` | 上传时选择 | `false` |
| **分块** | `chunking_mode` | 知识库设置 | `layout_aware` |
| | `chunk_size` | 知识库设置 | `512` |
| | `chunk_overlap` | 知识库设置 | `50` |
| **检索** | `top_k` | 聊天设置 | `10` |
| | `vector_weight` | 知识库设置 | `0.6` |
| | `keyword_weight` | 知识库设置 | `0.4` |
| **重排** | `reranker_provider` | 系统设置 | `cross_encoder` |
| | `rerank_threshold` | 知识库设置 | `0.0` |
| **生成** | `llm_provider` | 系统设置 | DB 配置 |
| | `temperature` | 聊天设置 | `0.1` |
| **算法** | `enable_raptor` | 知识库设置 | `false` |
| | `enable_graphrag` | 知识库设置 | `false` |

### 6.3 DB 模型 (多 Channel 支持)

```python
# server/models.py

class Channel(Base):
    """业务区域 (数据隔离单元)"""
    id: UUID
    name: str              # "legal", "product", "customer_service"
    display_name: str      # "法律合规部"
    description: str
    config: JSON           # Channel 级默认配置
    is_active: bool
    created_at: datetime

class Provider(Base):
    """Provider 配置（LLM/Embedding/Reranker/OCR）"""
    id: UUID
    channel_id: Optional[UUID]  # NULL = 全局可用
    name: str              # "openai", "dashscope"
    category: str          # "llm", "embedding", "reranker"
    base_url: str
    api_key: str           # 加密存储
    is_active: bool

class ModelConfig(Base):
    """模型配置"""
    id: UUID
    provider_id: UUID
    model_id: str          # "gpt-4o", "qwen-plus"
    name: str              # 显示名称
    type: str              # "chat", "embedding", "rerank"
    parameters: JSON       # 默认参数
    is_default: bool

class KBConfig(Base):
    """知识库配置"""
    id: UUID
    channel_id: UUID       # 所属 Channel (必填)
    name: str              # 在 Channel 内唯一
    display_name: str
    config: JSON           # 完整的 StrategyConfig
    created_at: datetime
    updated_at: datetime

class ChatSession(Base):
    """聊天会话"""
    id: UUID
    channel_id: UUID       # 所属 Channel
    user_id: UUID
    kb_ids: List[UUID]     # 绑定的 KB 列表 (多对多)
    config_override: JSON  # 运行时参数覆盖
    created_at: datetime
    updated_at: datetime

class ChatSessionKB(Base):
    """会话-知识库关联 (多对多)"""
    session_id: UUID
    kb_id: UUID
    priority: int          # 检索优先级
```

---

## 7. 存储层设计

### 7.1 存储组件矩阵

| 组件 | 职责 | 技术选型 | 容量规划 |
|:-----|:-----|:---------|:---------|
| **向量存储** | Chunk 向量 + Payload | Qdrant (主) / Milvus | 100TB (量化后 ~50TB) |
| **关键词索引** | 全文检索 + 过滤 | Elasticsearch | 10TB (压缩后) |
| **元数据** | KB/Doc/Model 配置 | PostgreSQL | 10GB |
| **对象存储** | 原始文件 / 中间产物 | MinIO / OSS | 100TB |
| **缓存** | 语义缓存 / 熔断状态 | Redis | 16GB |

### 7.2 单例模式与连接池

```python
# 所有存储客户端使用单例
class VectorStoreClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = QdrantClient(
                url=os.getenv("QDRANT_URL"),
                timeout=30,
                prefer_grpc=True  # 高性能
            )
        return cls._instance
```

---

## 8. 可观测性

### 8.1 监控架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Observability Stack                      │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Jaeger    │    │ Prometheus  │    │   Grafana   │     │
│  │  (Traces)   │    │  (Metrics)  │    │ (Dashboard) │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         │    ┌─────────────┴─────────────┐   │             │
│         │    │                           │   │             │
│         ▼    ▼                           ▼   ▼             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              OmniRAG Backend                        │   │
│  │  ┌──────────────┐  ┌────────────────────────────┐  │   │
│  │  │ OTel Tracer  │  │   Prometheus Metrics       │  │   │
│  │  │ (trace.py)   │  │   (monitor.py)             │  │   │
│  │  └──────────────┘  └────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 关键指标

```python
# core/utils/monitor.py
from prometheus_client import Counter, Histogram, Gauge

# 摄取指标
ingest_duration = Histogram('rag_ingest_duration_seconds', 'Ingest duration', ['stage'])
ingest_requests = Counter('rag_ingest_requests_total', 'Ingest requests', ['stage', 'status'])

# 检索指标
retrieval_latency = Histogram('rag_retrieval_latency_seconds', 'Retrieval latency')
reranker_latency = Histogram('rag_reranker_latency_seconds', 'Reranker latency')

# 缓存指标
cache_hit_rate = Gauge('rag_cache_hit_rate', 'Semantic cache hit rate')
embedding_cache_size = Gauge('rag_embedding_cache_size', 'Embedding cache size')

# 健康指标
hallucination_rate = Gauge('rag_hallucination_rate', 'Hallucination detection rate')
```

---

## 9. 部署架构

### 9.1 单节点开发环境

```bash
# scripts/dev.sh
uvicorn server.main:app --reload --port 8000 &
npm run dev --prefix frontend -- --port 5173 &
npm run dev --prefix embedded-ui -- --port 5174 &
```

### 9.2 生产环境 (Docker Compose)

```yaml
services:
  backend:
    build: .
    ports: ["8000:8000"]
    environment:
      - QDRANT_URL=http://qdrant:6333
      - ES_URL=http://elasticsearch:9200
      - DATABASE_URL=postgresql://...
    depends_on: [qdrant, elasticsearch, postgres, redis]

  qdrant:
    image: qdrant/qdrant:latest
    volumes: [qdrant_data:/qdrant/storage]

  elasticsearch:
    image: elasticsearch:8.11.0
    environment: ["discovery.type=single-node"]

  postgres:
    image: postgres:15-alpine

  redis:
    image: redis:7-alpine
```

### 9.3 Kubernetes (100TB 规模)

```yaml
# Qdrant 集群 (3 副本)
apiVersion: apps/v1
kind: StatefulSet
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: qdrant
        resources:
          limits: { memory: "32Gi", cpu: "16" }
        volumeMounts:
        - name: storage
          mountPath: /qdrant/storage
  volumeClaimTemplates:
  - spec:
      storageClassName: fast-ssd
      resources: { requests: { storage: 1Ti } }
```

---

## 10. 健康与可持续性

### 10.1 高可用策略

| 组件 | 策略 | 实现 |
|:-----|:-----|:-----|
| **向量库** | 多副本 + 分片 | Qdrant Cluster Mode |
| **LLM 调用** | 熔断 + 降级 | Circuit Breaker + Fallback Chain |
| **存储写入** | 双写 + 重试 | Index Router + Retry Policy |
| **任务处理** | 断点续传 | LangGraph Checkpointer |

### 10.2 代码质量守护

```
┌────────────────────────────────────────────────────────────┐
│                    Code Quality Gates                       │
│                                                             │
│  Pre-Commit                                                 │
│  ├── ruff format (代码格式)                                 │
│  ├── ruff check (linting)                                   │
│  └── mypy (类型检查)                                        │
│                                                             │
│  CI Pipeline                                                │
│  ├── pytest (单元测试 > 80%)                                │
│  ├── pytest --benchmark (性能回归)                          │
│  └── docker build (构建验证)                                │
│                                                             │
│  Deployment                                                 │
│  ├── Health Check (/api/health)                             │
│  ├── Canary Release (10% → 50% → 100%)                     │
│  └── Rollback Trigger (error_rate > 1%)                    │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 10.3 技术债务管理

| 债务项 | 优先级 | 状态 | 计划 |
|:-------|:-------|:-----|:-----|
| `core/nodes/` 遗留节点 | P1 | ⚠️ 已桥接 | V4 稳定后删除 |
| Redis 熔断状态持久化 | P2 | 🔴 待实现 | Sprint 2 |
| 语义缓存 Redis 化 | P2 | 🔴 待实现 | Sprint 2 |
| GraphRAG 实体抽取 | P3 | 🟡 骨架 | Sprint 3 |

---

## 11. 总结

本架构设计遵循以下核心目标：

1. **健康**: 单例模式避免资源泄漏，熔断降级保证稳定性
2. **可持续**: 分层设计、模块解耦、技术债务可追踪
3. **UI 可配置**: 三层配置覆盖，DB 驱动的 Provider 管理
4. **灵活交付**: LangGraph 可编排，策略可热切换，支持 A/B 测试

**关键设计决策**:
- LangGraph 作为管道编排核心
- State as Config 实现运行时灵活性
- Singleton + LRU 优化模型加载性能
- RRF 融合支持可配置权重
- 全链路可观测 (OTel + Prometheus)

---

*本文档与 `docs/tech/system-design.md` 保持对齐，如有冲突以 system-design.md 为准。*
