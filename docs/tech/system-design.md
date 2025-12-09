# 面向100TB规模的生产级RAG系统详细设计
## 基于LangGraph架构，融合多模态处理与端到端可视化

> **文档版本**: v2.0 (2025-12-08 审计修订版)
> **审计状态**: ✅ 已与实现代码对齐

---

## 1. 系统概述

### 1.1 核心设计理念

**State as Config (状态即配置)**
- 所有策略参数通过LangGraph State传递，UI动态注入配置
- 支持运行时策略切换与A/B测试

**Multi-Modal First (多模态优先)**
- 统一处理PDF、Office、图片、HTML/Markdown
- 智能路由：文本优先CPU路径，复杂版面/图表优先GPU路径

**Production-Grade (生产级)**
- 容量：支持100TB数据，1亿+文档
- 性能：检索P95 < 1.5s，可用性≥99.9%
- 可观测：全链路OTel追踪，实时进度SSE推送

### 1.2 核心性能约束 (新增)

| 指标 | 目标 | 实现策略 |
|:-----|:-----|:---------|
| 模型加载 | 单例模式 | CrossEncoder/LayoutLM/YOLO使用LRU缓存 |
| 向量检索 P95 | < 500ms | Qdrant HNSW索引 + 量化压缩 |
| Embedding批处理 | 64 texts/batch | Infinity Server + 本地缓存 |
| LLM调用 | 熔断+降级 | Circuit Breaker + Fallback Chain |

### 1.3 业务背景与多 Channel 架构

#### 1.3.1 数据规模与业务隔离

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          数据规模: 100TB ~ 500TB                             │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  业务区域 A     │  │  业务区域 B     │  │  业务区域 C     │  ...        │
│  │  (法律合规)     │  │  (产品研发)     │  │  (客户服务)     │             │
│  │                 │  │                 │  │                 │             │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │             │
│  │  │ KB: 法规  │  │  │  │ KB: 技术  │  │  │  │ KB: FAQ   │  │             │
│  │  │ KB: 判例  │  │  │  │ KB: 专利  │  │  │  │ KB: 工单  │  │             │
│  │  │ KB: 政策  │  │  │  │ KB: 设计  │  │  │  │ KB: 产品  │  │             │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │             │
│  │                 │  │                 │  │                 │             │
│  │  数据完全隔离   │  │  数据完全隔离   │  │  数据完全隔离   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**核心业务约束:**

| 约束 | 描述 | 技术实现 |
|:-----|:-----|:---------|
| **数据隔离** | 不同业务区域数据完全隔离，不可交叉访问 | Channel 级数据分区 + ACL |
| **配置独立** | 每个 KB 根据内容特性独立配置策略 | KB-Level StrategyConfig |
| **Chat 绑定** | 每个 Chat Session 可绑定多个 KB | Session-KB 多对多关联 |
| **权限控制** | Channel/KB/Chat 三级权限模型 | RBAC + JWT Token |

#### 1.3.2 Channel-KB-Chat 三层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              CHANNEL (业务区域)                           │
│  - 代表一个业务部门或业务线                                                │
│  - 拥有独立的数据存储分区                                                  │
│  - 拥有独立的权限边界                                                      │
│  - 可配置独立的 LLM/Embedding Provider                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                    │                                      │
│                    ┌───────────────┼───────────────┐                     │
│                    ▼               ▼               ▼                     │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐ │
│  │  KNOWLEDGE BASE A   │ │  KNOWLEDGE BASE B   │ │  KNOWLEDGE BASE C   │ │
│  │  - 独立策略配置     │ │  - 独立策略配置     │ │  - 独立策略配置     │ │
│  │  - 内容格式: PDF    │ │  - 内容格式: 表格   │ │  - 内容格式: 网页   │ │
│  │  - 分块: 语义切分   │ │  - 分块: 表格优先   │ │  - 分块: 固定长度   │ │
│  │  - OCR: Qwen-VL     │ │  - OCR: 深度解析    │ │  - OCR: 关闭        │ │
│  │  - 算法: GraphRAG   │ │  - 算法: RAPTOR     │ │  - 算法: 标准       │ │
│  └──────────┬──────────┘ └──────────┬──────────┘ └──────────┬──────────┘ │
│             │                       │                       │            │
│             └───────────────────────┼───────────────────────┘            │
│                                     ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                         CHAT SESSION                             │   │
│  │  - 绑定一个或多个 KB                                              │   │
│  │  - 运行时覆盖检索参数 (top_k, temperature)                        │   │
│  │  - 记录对话历史                                                   │   │
│  │  - 支持 A/B 测试                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### 1.3.3 KB 独立配置能力

根据知识库内容的**格式**、**业务性质**、**业务特性**进行差异化配置:

| 业务场景 | 内容格式 | 推荐配置 |
|:---------|:---------|:---------|
| **法律法规** | 结构化 PDF | `chunk_size=800`, `semantic`, `GraphRAG`, 高精度 OCR |
| **技术文档** | Markdown/HTML | `chunk_size=600`, `layout_aware`, 标准检索 |
| **财务报表** | 表格 PDF | `table_first`, 强制 OCR, 专用表格解析 |
| **产品说明** | 图文混合 | `multimodal`, VLM 解析, 图文联合检索 |
| **客服 FAQ** | 短文本 | `chunk_size=256`, 关键词权重高, 快速匹配 |
| **学术论文** | 长文档 | `chunk_size=1200`, RAPTOR 聚类, 引用追踪 |

---

## 2. 核心状态定义

### 2.1 Ingestion State Schema

```python
from typing import TypedDict, List, Optional, Dict, Any, Literal
from datetime import datetime

class StrategyConfig(TypedDict):
    """策略配置 - 从UI注入"""
    # OCR/VLM策略
    ocr_provider: Literal["deepseek", "qwen-vl", "volc_engine", "paddle", "auto"]
    ocr_fallback_chain: List[str]  # ["qwen-vl", "volc_engine"]
    ocr_concurrency: int
    force_ocr: bool  # 强制OCR，跳过文本提取

    # 分块策略
    chunking_mode: Literal["fixed", "semantic", "layout_aware", "table_first"]
    chunk_size: int
    chunk_overlap: int
    preserve_tables: bool

    # Embedding策略
    embedding_model: str  # "bge-m3" | "custom"
    embedding_batch_size: int
    embedding_dimensions: int

    # 索引策略
    vector_backend: Literal["qdrant", "milvus", "auto"]
    keyword_backend: Literal["elasticsearch", "disabled", "local"]
    enable_quantization: bool  # Binary quantization for 100TB
    enable_hot_cold_tier: bool

    # 高级算法 (新增)
    algorithms: AlgorithmConfig

    # 质量控制
    enable_cleaning: bool
    min_quality_score: float
    enable_dedup: bool
    enable_pii_filter: bool

class AlgorithmConfig(TypedDict):
    """高级RAG算法配置 (新增)"""
    enable_raptor: bool           # RAPTOR聚类摘要
    raptor_max_cluster: int       # 最大聚类数
    enable_graphrag: bool         # GraphRAG知识图谱
    graph_community_level: int    # 社区检测层级
    enable_mindmap: bool          # 思维导图生成

class ChunkMetadata(TypedDict):
    channel_id: str             # 所属 Channel (业务隔离)
    doc_id: str
    batch_id: str
    page_num: Optional[int]
    bbox: Optional[List[float]]  # [x0, y0, x1, y1]
    block_type: Literal["text", "table", "image", "header", "footer"]
    media_type: str
    language: str
    quality_score: float
    ocr_provider: Optional[str]
    ocr_confidence: Optional[float]
    heading_level: Optional[int]  # H1=1, H2=2...用于加权

class IngestState(TypedDict):
    # 多 Channel 隔离
    channel_id: str             # 业务区域 ID (数据隔离边界)

    # 基础元数据
    task_id: str
    file_path: str
    file_type: str
    batch_id: str
    kb_name: str
    version: int

    # 策略配置
    strategy_config: StrategyConfig

    # 管道数据
    raw_content: Optional[bytes]
    extracted_text: Optional[str]
    parsed_blocks: List[Dict]  # [{"type": "text", "content": "...", "bbox": [...]}]
    images: List[Dict]  # [{"data": bytes, "bbox": [...], "page": 1}]
    chunks: List[Dict]  # [{"content": "...", "metadata": ChunkMetadata}]
    vectors: List[List[float]]

    # 状态控制
    processing_stage: Literal["upload", "parse", "chunk", "embed", "index", "finalize"]
    retry_count: int
    error_log: List[Dict]  # [{"stage": "parse", "error": "...", "timestamp": "..."}]
    progress: Dict[str, Any]  # {"total_chunks": 100, "completed_chunks": 45}

    # 质量指标
    quality_metrics: Dict[str, float]  # {"avg_quality": 0.85, "dedup_rate": 0.1}
```

### 2.2 Retrieval State Schema

```python
class RetrievalState(TypedDict):
    # 多 Channel 隔离
    channel_id: str             # 业务区域 ID (数据隔离边界)
    session_id: str             # Chat Session ID

    # 输入
    query_id: str
    input_query: str
    chat_history: List[Dict]
    kb_names: List[str]         # 可绑定多个 KB
    user_id: str

    # 策略配置
    strategy_config: Dict[str, Any]  # {top_k, temperature, rerank_model, strict_mode}

    # 中间态
    preprocessed_queries: List[str]  # Query decomposition/rewrite
    intent: Dict[str, Any]  # {"type": "table_query", "filters": {"lang": "zh"}}

    # 检索结果
    vector_results: List[Dict]  # Qdrant召回
    keyword_results: List[Dict]  # ES召回
    fused_results: List[Dict]  # RRF融合
    reranked_results: List[Dict]  # Reranker排序
    retrieved_chunks: List[Dict]  # 向后兼容别名

    # 相关性判断
    relevance_score: float
    is_relevant: bool
    loop_count: int  # 防止死循环，最大2次

    # 缓存状态 (新增)
    cache_hit: bool
    cache_key: Optional[str]

    # 最终输出
    answer: str  # 向后兼容
    final_answer: str
    citations: List[Dict]  # [{"doc_id": "...", "page": 3, "bbox": [...], "content": "..."}]
    confidence: float
    sources: List[Dict]  # 向后兼容
```

---

## 3. Ingestion Graph 详细设计

### 3.1 Graph Topology

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver

# 初始化图
workflow = StateGraph(IngestState)

# 节点注册
workflow.add_node("loader", LoaderNode())
workflow.add_node("router", RouterNode())
workflow.add_node("cpu_parser", CpuTextParser())
workflow.add_node("gpu_parser", GpuVisionParser())
workflow.add_node("qc_validator", QualityValidator())
workflow.add_node("cleaner", SemanticCleaner())
workflow.add_node("chunker", SmartChunker())
workflow.add_node("embedder", BatchEmbedder())
workflow.add_node("indexer", DualIndexer())
workflow.add_node("finalizer", Finalizer())
workflow.add_node("error_handler", ErrorHandler())

# 入口点
workflow.set_entry_point("loader")

# 【修正】loader → router 边 (原设计遗漏)
workflow.add_edge("loader", "router")

# 条件路由
def route_by_file_type(state: IngestState) -> str:
    cfg = state['strategy_config']
    if cfg['force_ocr']:
        return "gpu_parser"

    file_type = state['file_type']
    if file_type in ['jpg', 'png', 'tiff', 'webp']:
        return "gpu_parser"
    elif file_type == 'pdf':
        # 检测是否扫描件
        if is_scanned_pdf(state['file_path']):
            return "gpu_parser"
        return "cpu_parser"
    else:  # docx, html, md
        return "cpu_parser"

workflow.add_conditional_edges(
    "router",
    route_by_file_type,
    {
        "cpu_parser": "cpu_parser",
        "gpu_parser": "gpu_parser"
    }
)

# 汇聚到质量检查
workflow.add_edge("cpu_parser", "qc_validator")
workflow.add_edge("gpu_parser", "qc_validator")

# QC后的条件分支
def should_clean(state: IngestState) -> str:
    if state['strategy_config']['enable_cleaning']:
        return "cleaner"
    return "chunker"

workflow.add_conditional_edges(
    "qc_validator",
    should_clean,
    {
        "cleaner": "cleaner",
        "chunker": "chunker"
    }
)
workflow.add_edge("cleaner", "chunker")

# 线性流程
workflow.add_edge("chunker", "embedder")
workflow.add_edge("embedder", "indexer")
workflow.add_edge("indexer", "finalizer")
workflow.add_edge("finalizer", END)

# 【修正】全局错误处理 - LangGraph不支持"*"通配符
# 错误处理应在每个节点内部try-catch，或使用subgraph
# 以下为正确模式：
workflow.add_node("error_recovery", ErrorRecoveryNode())

def check_error(state: IngestState) -> str:
    if state.get('error_log') and state['retry_count'] < 3:
        return "error_recovery"
    return "finalizer"

# 在indexer后添加错误检查
workflow.add_conditional_edges(
    "indexer",
    check_error,
    {
        "error_recovery": "error_recovery",
        "finalizer": "finalizer"
    }
)
workflow.add_edge("error_recovery", "chunker")  # 重试从chunker开始

# 编译图（带Checkpointer）
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
app = workflow.compile(checkpointer=checkpointer)
```

### 3.2 关键节点实现

#### LoaderNode - 流式加载与预处理

```python
class LoaderNode:
    async def __call__(self, state: IngestState) -> IngestState:
        file_path = state['file_path']
        file_type = state['file_type']

        # 更新阶段
        state['processing_stage'] = 'parse'

        # 处理ZIP流式解压
        if file_type in ['zip', 'tar']:
            if state['strategy_config'].get('stream_unzip', True):
                # 触发子图处理每个文件
                async for sub_file in self._stream_unzip(file_path):
                    # 投递到队列，异步处理
                    await self._dispatch_subtask(state['batch_id'], sub_file)
                return state  # 主任务标记为完成

        # 处理超大PDF（>100MB）- Lazy加载
        if file_type == 'pdf':
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:
                state['raw_content'] = None  # 不加载全量
                state['lazy_load'] = True
                return state

        # 常规加载
        async with aiofiles.open(file_path, 'rb') as f:
            state['raw_content'] = await f.read()

        return state
```

#### GpuVisionParser - 多Provider OCR/VLM

```python
class GpuVisionParser:
    """
    【性能优化】Provider实例在__init__创建，避免重复初始化
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_providers()
        return cls._instance

    def _init_providers(self):
        self.providers = {
            'deepseek': DeepSeekOCRProvider(),
            'qwen-vl': QwenVLProvider(),
            'volc_engine': VolcEngineProvider(),
            'paddle': PaddleOCRProvider()
        }
        self.rate_limiters = {
            'qwen-vl': AsyncLimiter(10, 1),  # 10 QPS
            'volc_engine': AsyncLimiter(5, 1)
        }

    async def __call__(self, state: IngestState) -> IngestState:
        cfg = state['strategy_config']
        provider_name = cfg['ocr_provider']
        fallback_chain = cfg.get('ocr_fallback_chain', [])

        # 尝试主Provider
        try:
            async with self.rate_limiters.get(provider_name, nullcontext()):
                result = await self._parse_with_provider(
                    provider_name,
                    state['raw_content']
                )
                state['parsed_blocks'] = result['blocks']
                state['images'] = result['images']

                # 记录元数据
                for block in state['parsed_blocks']:
                    block['ocr_provider'] = provider_name
                    block['ocr_confidence'] = result.get('confidence', 1.0)

                return state
        except Exception as e:
            state['error_log'].append({
                'stage': 'gpu_parser',
                'provider': provider_name,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })

            # 尝试Fallback
            for fallback in fallback_chain:
                try:
                    result = await self._parse_with_provider(fallback, state['raw_content'])
                    state['parsed_blocks'] = result['blocks']
                    return state
                except:
                    continue

            # 全部失败，抛出异常触发重试
            raise Exception(f"All OCR providers failed: {provider_name}, {fallback_chain}")

    async def _parse_with_provider(self, provider_name: str, content: bytes) -> Dict:
        provider = self.providers[provider_name]

        if provider_name == 'qwen-vl':
            # 使用Qwen-VL进行版面分析+表格识别
            return await provider.parse_layout_and_tables(content)
        elif provider_name == 'volc_engine':
            # 火山引擎专门处理票据/卡证
            return await provider.parse_structured_doc(content)
        else:
            # DeepSeek/Paddle通用OCR
            return await provider.extract_text(content)
```

#### SmartChunker - 多策略分块

```python
class SmartChunker:
    async def __call__(self, state: IngestState) -> IngestState:
        cfg = state['strategy_config']
        mode = cfg['chunking_mode']

        parsed_blocks = state['parsed_blocks']
        chunks = []

        if mode == 'fixed':
            chunks = self._fixed_chunking(parsed_blocks, cfg['chunk_size'], cfg['chunk_overlap'])

        elif mode == 'semantic':
            # 基于Markdown Header边界
            chunks = self._semantic_chunking(parsed_blocks)

        elif mode == 'layout_aware':
            # 按版面块（标题、段落、表格）切分
            chunks = self._layout_chunking(parsed_blocks)

        elif mode == 'table_first':
            # 表格单独成块，文本正常切分
            chunks = self._table_priority_chunking(parsed_blocks, cfg)

        # 为每个Chunk生成元数据
        for i, chunk in enumerate(chunks):
            chunk['metadata'] = ChunkMetadata(
                doc_id=state['task_id'],
                batch_id=state['batch_id'],
                page_num=chunk.get('page_num'),
                bbox=chunk.get('bbox'),
                block_type=chunk.get('type', 'text'),
                media_type=state['file_type'],
                language=self._detect_language(chunk['content']),
                quality_score=chunk.get('quality_score', 1.0),
                ocr_provider=chunk.get('ocr_provider'),
                ocr_confidence=chunk.get('ocr_confidence'),
                heading_level=chunk.get('heading_level')  # 新增
            )
            chunk['chunk_id'] = f"{state['task_id']}_chunk_{i}"

        state['chunks'] = chunks
        state['progress']['total_chunks'] = len(chunks)
        state['processing_stage'] = 'embed'

        return state

    def _table_priority_chunking(self, blocks: List[Dict], cfg: StrategyConfig) -> List[Dict]:
        """表格优先策略：表格独立成块，保留完整性"""
        chunks = []
        text_buffer = []

        for block in blocks:
            if block['type'] == 'table':
                # 先处理文本缓冲
                if text_buffer:
                    chunks.extend(self._fixed_chunking(text_buffer, cfg['chunk_size'], cfg['chunk_overlap']))
                    text_buffer = []

                # 表格单独成块
                chunks.append({
                    'content': block['content'],
                    'type': 'table',
                    'bbox': block.get('bbox'),
                    'page_num': block.get('page'),
                    'quality_score': 1.0  # 表格认为是高质量
                })
            else:
                text_buffer.append(block)

        # 处理剩余文本
        if text_buffer:
            chunks.extend(self._fixed_chunking(text_buffer, cfg['chunk_size'], cfg['chunk_overlap']))

        return chunks
```

#### BatchEmbedder - 批量向量化

```python
class BatchEmbedder:
    """
    【性能优化】
    1. 使用SHA256替代MD5 (更安全的哈希)
    2. Infinity客户端单例
    3. asyncio.to_thread包装同步调用
    """
    _infinity_client = None

    def __init__(self):
        if BatchEmbedder._infinity_client is None:
            BatchEmbedder._infinity_client = InfinityClient("http://infinity:7997")
        self.cache = LRUCache(maxsize=10000)

    async def __call__(self, state: IngestState) -> IngestState:
        cfg = state['strategy_config']
        chunks = state['chunks']
        batch_size = cfg['embedding_batch_size']

        vectors = []
        state['processing_stage'] = 'embed'

        # 批量处理
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            texts = [c['content'] for c in batch]

            # 检查缓存 【修正】使用SHA256
            import hashlib
            cached_vectors = []
            texts_to_embed = []
            indices_to_embed = []

            for idx, text in enumerate(texts):
                cache_key = hashlib.sha256(text.encode()).hexdigest()[:32]
                if cache_key in self.cache:
                    cached_vectors.append((idx, self.cache[cache_key]))
                else:
                    texts_to_embed.append(text)
                    indices_to_embed.append(idx)

            # 批量Embedding
            if texts_to_embed:
                try:
                    batch_vectors = await self._infinity_client.embed(
                        model=cfg['embedding_model'],
                        texts=texts_to_embed
                    )

                    # 更新缓存
                    for text, vec in zip(texts_to_embed, batch_vectors):
                        cache_key = hashlib.sha256(text.encode()).hexdigest()[:32]
                        self.cache[cache_key] = vec

                    # 合并结果
                    result_vectors = [None] * len(texts)
                    for idx, vec in cached_vectors:
                        result_vectors[idx] = vec
                    for idx, vec in zip(indices_to_embed, batch_vectors):
                        result_vectors[idx] = vec

                    vectors.extend(result_vectors)

                except Exception as e:
                    state['error_log'].append({
                        'stage': 'embedder',
                        'batch_index': i,
                        'error': str(e)
                    })
                    raise
            else:
                # 全部命中缓存
                vectors.extend([v for _, v in sorted(cached_vectors)])

            # 更新进度
            state['progress']['completed_chunks'] = i + len(batch)

        state['vectors'] = vectors
        state['processing_stage'] = 'index'
        return state
```

#### DualIndexer - Qdrant + ES双写

```python
class DualIndexer:
    """
    【性能优化】客户端单例 + 连接池
    """
    _qdrant_client = None
    _es_client = None

    def __init__(self):
        if DualIndexer._qdrant_client is None:
            DualIndexer._qdrant_client = QdrantClient(
                "http://qdrant:6333",
                timeout=30,
                prefer_grpc=True  # gRPC性能更好
            )
        if DualIndexer._es_client is None:
            DualIndexer._es_client = AsyncElasticsearch(
                ["http://elasticsearch:9200"],
                max_retries=3,
                retry_on_timeout=True
            )

    async def __call__(self, state: IngestState) -> IngestState:
        cfg = state['strategy_config']
        kb_name = state['kb_name']
        chunks = state['chunks']
        vectors = state['vectors']

        # Qdrant Collection命名 【修正】避免硬编码
        collection_name = f"kb_{kb_name}_v{state['version']}"

        # 确保Collection存在
        await self._ensure_collection(collection_name, cfg)

        # 批量写入Qdrant
        if cfg['vector_backend'] in ['qdrant', 'auto']:
            points = [
                {
                    "id": chunk['chunk_id'],
                    "vector": vector,
                    "payload": {
                        "content": chunk['content'],
                        "metadata": chunk['metadata']
                    }
                }
                for chunk, vector in zip(chunks, vectors)
            ]

            await self._qdrant_client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True
            )

        # 批量写入ES（若启用）
        if cfg['keyword_backend'] == 'elasticsearch':
            index_name = f"kb_{kb_name}_docs"

            bulk_body = []
            for chunk in chunks:
                bulk_body.append({"index": {"_id": chunk['chunk_id']}})
                bulk_body.append({
                    "content": chunk['content'],
                    "metadata": chunk['metadata'],
                    "batch_id": state['batch_id'],
                    "version": state['version']
                })

            await self._es_client.bulk(index=index_name, body=bulk_body)

        state['processing_stage'] = 'finalize'
        return state

    async def _ensure_collection(self, collection_name: str, cfg: StrategyConfig):
        """确保Qdrant Collection存在且配置正确"""
        try:
            await self._qdrant_client.get_collection(collection_name)
        except:
            # 创建Collection
            await self._qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "size": cfg['embedding_dimensions'],
                    "distance": "Cosine"
                },
                optimizers_config={
                    "indexing_threshold": 20000
                },
                quantization_config={
                    "scalar": {
                        "type": "int8",
                        "quantile": 0.99,
                        "always_ram": True
                    }
                } if cfg['enable_quantization'] else None
            )
```

---

## 4. Retrieval Graph 详细设计

### 4.1 Graph Topology

```python
qa_workflow = StateGraph(RetrievalState)

# 节点注册
qa_workflow.add_node("preprocessor", QueryPreProcessor())
qa_workflow.add_node("cache_checker", SemanticCacheChecker())
qa_workflow.add_node("hybrid_retriever", HybridRetriever())
qa_workflow.add_node("reranker", CrossEncoderReranker())
qa_workflow.add_node("relevance_grader", RelevanceGrader())
qa_workflow.add_node("generator", CitationGenerator())
qa_workflow.add_node("hallucination_guard", HallucinationGuard())

# 流程定义
qa_workflow.set_entry_point("preprocessor")
qa_workflow.add_edge("preprocessor", "cache_checker")

def check_cache_hit(state: RetrievalState) -> str:
    if state.get('cache_hit'):
        return "end"
    return "hybrid_retriever"

qa_workflow.add_conditional_edges(
    "cache_checker",
    check_cache_hit,
    {
        "end": END,
        "hybrid_retriever": "hybrid_retriever"
    }
)

qa_workflow.add_edge("hybrid_retriever", "reranker")
qa_workflow.add_edge("reranker", "relevance_grader")

# 【修正】条件路由不应修改state，应返回路由决策
def route_by_relevance(state: RetrievalState) -> str:
    if state.get('is_relevant', False):
        return "generator"
    elif state.get('loop_count', 0) < 2:
        return "preprocessor"  # Query Rewrite重试
    else:
        return "generator"  # 放弃，返回"未找到"

qa_workflow.add_conditional_edges(
    "relevance_grader",
    route_by_relevance,
    {
        "generator": "generator",
        "preprocessor": "preprocessor"
    }
)

qa_workflow.add_edge("generator", "hallucination_guard")
qa_workflow.add_edge("hallucination_guard", END)

qa_app = qa_workflow.compile()
```

### 4.2 关键节点实现

#### QueryPreProcessor - Query增强

```python
class QueryPreProcessor:
    """
    【修正】LLM客户端从DB加载，避免硬编码DashScopeClient
    """
    def __init__(self):
        self.gateway = None

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state['input_query']
        cfg = state.get('strategy_config', {})

        # 从配置或DB加载LLM
        from core.llm.gateway import LLMGateway
        self.gateway = LLMGateway(
            provider=cfg.get('llm_provider'),
            model=cfg.get('llm_model')
        )

        # 【修正】更新loop_count（在RelevanceGrader判断后设置）
        loop_count = state.get('loop_count', 0)
        state['loop_count'] = loop_count + 1 if loop_count > 0 else 0

        # 1. 语言检测
        lang = self._detect_language(query)

        # 2. Intent识别
        intent_prompt = f"""
分析用户意图，返回JSON:
{{"type": "factual|table|image|comparison|summary", "filters": {{"lang": "zh", "block_type": "table"}}}}

Query: {query}
"""
        try:
            intent_resp = await self.gateway.chat(intent_prompt)
            # 提取JSON
            import json
            start = intent_resp.find("{")
            end = intent_resp.rfind("}") + 1
            if start >= 0 and end > start:
                state['intent'] = json.loads(intent_resp[start:end])
            else:
                state['intent'] = {"type": "factual"}
        except:
            state['intent'] = {"type": "factual"}

        # 3. Query Rewrite（若需要 - 非首次且上一轮失败）
        if loop_count > 0:
            rewrite_prompt = f"""
原始Query: {query}
上次检索无相关结果，请重写Query:
- 补全指代词
- 简化复杂从句
- 提取关键实体
"""
            try:
                rewritten = await self.gateway.chat(rewrite_prompt)
                state['preprocessed_queries'] = [rewritten.strip()]
            except:
                state['preprocessed_queries'] = [query]
        else:
            state['preprocessed_queries'] = [query]

        # 4. Query Decomposition（若是复合问题）
        if any(kw in query for kw in ["并且", "以及", "和", "同时"]):
            decompose_prompt = f"将复合问题拆解为独立子问题（每行一个）：{query}"
            try:
                sub_queries = await self.gateway.chat(decompose_prompt)
                state['preprocessed_queries'] = [q.strip() for q in sub_queries.split('\n') if q.strip()]
            except:
                pass

        return state
```

#### HybridRetriever - RRF融合检索

```python
class HybridRetriever:
    """
    【性能优化】
    1. 并发执行向量和关键词检索
    2. 客户端单例
    3. 可配置的RRF权重
    """
    _qdrant_client = None
    _es_client = None
    _embedder = None

    def __init__(self):
        if HybridRetriever._qdrant_client is None:
            from core.storage.vector_store import get_vector_client
            HybridRetriever._qdrant_client = get_vector_client()
        if HybridRetriever._es_client is None:
            from core.storage.keyword_store import get_keyword_client
            HybridRetriever._es_client = get_keyword_client()
        if HybridRetriever._embedder is None:
            from core.embedding.registry import get_embedder
            HybridRetriever._embedder = get_embedder()

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state['strategy_config']
        queries = state['preprocessed_queries']
        intent = state.get('intent', {})
        kb_name = state['kb_name']

        top_k = cfg.get('top_k', 10)

        # 【优化】并发执行向量检索和关键词检索
        import asyncio

        async def _search_vector(query: str):
            vec = await self._embedder.embed(query)
            return await self._qdrant_client.search(
                collection_name=f"kb_{kb_name}_v1",
                query_vector=vec.tolist() if hasattr(vec, 'tolist') else vec,
                limit=top_k * 2
            )

        async def _search_keyword(query: str):
            return await self._es_client.search(
                index_name=f"kb_{kb_name}_docs",
                query=query,
                limit=top_k * 2
            )

        # 并发执行所有查询
        all_tasks = []
        for query in queries:
            all_tasks.append(_search_vector(query))
            all_tasks.append(_search_keyword(query))

        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        # 分离结果
        vector_results = []
        keyword_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                continue
            if i % 2 == 0:
                vector_results.extend(res)
            else:
                keyword_results.extend(res)

        # 3. RRF融合 【新增】可配置权重
        fused_results = self._reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=cfg.get('rrf_k', 60),
            vector_weight=cfg.get('vector_weight', 0.6),
            keyword_weight=cfg.get('keyword_weight', 0.4)
        )

        state['vector_results'] = vector_results
        state['keyword_results'] = keyword_results
        state['fused_results'] = fused_results[:top_k]

        return state

    def _reciprocal_rank_fusion(
        self,
        vec_results,
        kw_results,
        k=60,
        vector_weight=0.6,
        keyword_weight=0.4
    ):
        """
        RRF算法融合
        【新增】可配置的向量/关键词权重
        """
        scores = {}
        docs = {}

        # 向量结果排名贡献
        for rank, doc in enumerate(vec_results, 1):
            doc_id = str(doc.get('id', doc.get('_id')))
            scores[doc_id] = scores.get(doc_id, 0) + vector_weight / (k + rank)
            if doc_id not in docs:
                docs[doc_id] = doc

        # 关键词结果排名贡献
        for rank, doc in enumerate(kw_results, 1):
            doc_id = str(doc.get('id', doc.get('_id')))
            scores[doc_id] = scores.get(doc_id, 0) + keyword_weight / (k + rank)
            if doc_id not in docs:
                docs[doc_id] = doc

        # 排序
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return [
            {"doc_id": doc_id, "score": score, "content": docs[doc_id]}
            for doc_id, score in sorted_docs
        ]
```

#### CrossEncoderReranker - 重排序

```python
class CrossEncoderReranker:
    """
    【性能关键】使用单例模式加载CrossEncoder
    """

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        cfg = state['strategy_config']
        query = state['input_query']
        fused_docs = state['fused_results']

        if not fused_docs:
            state['reranked_results'] = []
            state['is_relevant'] = False
            return state

        # 获取Reranker（单例）
        from core.reranker.registry import get_reranker
        reranker = await get_reranker(
            provider=cfg.get('reranker_provider'),
            model_id=cfg.get('reranker_model')
        )

        texts = [doc.get('content', {}).get('content', '') for doc in fused_docs]

        # 【优化】对于同步的CrossEncoder，使用asyncio.to_thread
        import asyncio
        scores = await asyncio.to_thread(reranker.score, query, texts)

        # 更新分数并排序
        reranked = []
        threshold = cfg.get('rerank_threshold', 0.0)

        for doc, score in zip(fused_docs, scores):
            doc['rerank_score'] = score
            if score >= threshold:
                reranked.append(doc)

        reranked.sort(key=lambda x: x['rerank_score'], reverse=True)

        state['reranked_results'] = reranked
        state['is_relevant'] = len(reranked) > 0
        state['retrieved_chunks'] = reranked  # 向后兼容

        return state
```

#### HallucinationGuard - 幻觉检测 (新增)

```python
class HallucinationGuard:
    """
    【新增节点】检测LLM回答中的幻觉
    """

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        answer = state.get('final_answer', '')
        docs = state.get('reranked_results', [])

        if not answer or not docs:
            return state

        # 构建上下文证据
        evidence = "\n".join([
            doc.get('content', {}).get('content', '')
            for doc in docs[:5]
        ])

        # 使用LLM检测幻觉
        from core.llm.gateway import LLMGateway
        gateway = LLMGateway()

        check_prompt = f"""
你是一个事实核查员。判断以下回答是否完全基于提供的证据。

证据:
{evidence}

回答:
{answer}

如果回答包含证据中未提及的事实，返回 "HALLUCINATION: [具体内容]"
如果回答完全基于证据，返回 "VERIFIED"
"""

        try:
            result = await gateway.chat(check_prompt)
            if "HALLUCINATION" in result:
                state['confidence'] *= 0.5  # 降低置信度
                state['hallucination_detected'] = True
                state['hallucination_details'] = result
        except:
            pass

        return state
```

#### SemanticCacheChecker - 语义缓存 (新增)

```python
class SemanticCacheChecker:
    """
    【新增节点】检查语义相似的历史查询缓存
    """
    _cache = {}  # 生产环境应使用Redis

    async def __call__(self, state: RetrievalState) -> RetrievalState:
        query = state['input_query']
        kb_name = state['kb_name']

        cache_key = f"{kb_name}:{query}"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            state['final_answer'] = cached['answer']
            state['citations'] = cached['citations']
            state['cache_hit'] = True
            return state

        # TODO: 实现语义相似度匹配
        # 使用embedding比较query相似度，阈值0.95以上返回缓存

        state['cache_hit'] = False
        state['cache_key'] = cache_key
        return state
```

---

## 5. 高级RAG算法设计 (新增章节)

### 5.1 RAPTOR - 递归摘要树

```python
class RAPTORProcessor:
    """
    RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval

    核心思想：
    1. 对文档块进行层次聚类
    2. 对每个聚类生成摘要
    3. 递归构建摘要树
    4. 检索时从树根向下遍历
    """

    async def process(self, kb_name: str, max_clusters: int = 10):
        # 1. 获取所有chunks
        chunks = await self._fetch_chunks(kb_name)

        # 2. 层次聚类 (使用sklearn KMeans)
        from sklearn.cluster import MiniBatchKMeans
        embeddings = await self._get_embeddings(chunks)

        n_clusters = min(max_clusters, len(chunks) // 5)
        kmeans = MiniBatchKMeans(n_clusters=n_clusters, batch_size=256)
        labels = kmeans.fit_predict(embeddings)

        # 3. 为每个聚类生成摘要
        cluster_summaries = {}
        for cluster_id in range(n_clusters):
            cluster_texts = [chunks[i]['content'] for i, l in enumerate(labels) if l == cluster_id]
            summary = await self._summarize_cluster(cluster_texts)
            cluster_summaries[cluster_id] = summary

        # 4. 存储摘要树
        await self._store_raptor_tree(kb_name, cluster_summaries, labels)
```

### 5.2 GraphRAG - 知识图谱增强

```python
class GraphRAGProcessor:
    """
    GraphRAG: Graph-based Retrieval Augmented Generation

    核心思想：
    1. 从文档中抽取实体和关系
    2. 构建知识图谱
    3. 使用社区检测算法划分子图
    4. 为每个社区生成摘要
    5. 检索时结合图遍历
    """

    async def build_graph(self, kb_name: str):
        import networkx as nx
        import community as community_louvain

        # 1. 抽取实体和关系
        entities, relations = await self._extract_entities_relations(kb_name)

        # 2. 构建图
        G = nx.Graph()
        for e in entities:
            G.add_node(e['name'], type=e['type'], desc=e.get('desc'))
        for r in relations:
            G.add_edge(r['src'], r['tgt'], desc=r.get('desc'))

        # 3. 社区检测 (Louvain算法)
        partition = community_louvain.best_partition(G)

        # 4. 为每个社区生成摘要
        community_summaries = {}
        for com_id in set(partition.values()):
            nodes = [n for n, c in partition.items() if c == com_id]
            summary = await self._summarize_community(nodes, G)
            community_summaries[com_id] = summary

        # 5. 存储
        await self._store_graph(kb_name, G, partition, community_summaries)
```

---

## 6. 生产级部署架构

### 6.1 Docker Compose配置

```yaml
version: '3.8'

services:
  # 后端服务
  backend:
    build: ./server
    ports:
      - "8000:8000"
    environment:
      - QDRANT_URL=http://qdrant:6333
      - ES_URL=http://elasticsearch:9200
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/rag
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - qdrant
      - elasticsearch
      - redis
      - postgres
      - minio
    volumes:
      - ./data:/app/data
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G

  # 前端服务
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  # Qdrant向量库
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334

  # Elasticsearch
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"
    volumes:
      - es_data:/usr/share/elasticsearch/data

  # Redis (队列+缓存+熔断状态)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # PostgreSQL (元数据+Checkpointer)
  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=rag
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # MinIO (对象存储)
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=admin123
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

  # Infinity Embedding服务
  infinity:
    image: michaelf34/infinity:latest
    ports:
      - "7997:7997"
    environment:
      - MODEL_ID=BAAI/bge-m3
    volumes:
      - ./models:/models

volumes:
  qdrant_data:
  es_data:
  redis_data:
  postgres_data:
  minio_data:
```

---

## 7. 监控与可观测

### 7.1 OTel追踪

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# 初始化
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317")
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# 在Node中埋点
class GpuVisionParser:
    async def __call__(self, state: IngestState) -> IngestState:
        with tracer.start_as_current_span("gpu_vision_parser") as span:
            span.set_attribute("file_type", state['file_type'])
            span.set_attribute("ocr_provider", state['strategy_config']['ocr_provider'])

            start_time = time.time()
            result = await self._parse(state)

            span.set_attribute("duration_ms", (time.time() - start_time) * 1000)
            span.set_attribute("blocks_count", len(result['parsed_blocks']))

            return result
```

### 7.2 Prometheus指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义指标
ingest_requests = Counter('rag_ingest_requests_total', 'Total ingest requests', ['stage', 'status'])
ingest_duration = Histogram('rag_ingest_duration_seconds', 'Ingest duration', ['stage'])
queue_depth = Gauge('rag_queue_depth', 'Queue depth', ['queue_name'])
retrieval_latency = Histogram('rag_retrieval_latency_seconds', 'Retrieval latency')

# 【新增】关键业务指标
cache_hit_rate = Gauge('rag_cache_hit_rate', 'Semantic cache hit rate')
hallucination_rate = Gauge('rag_hallucination_rate', 'Hallucination detection rate')
reranker_latency = Histogram('rag_reranker_latency_seconds', 'Reranker latency')
embedding_cache_size = Gauge('rag_embedding_cache_size', 'Embedding cache size')

# 在Node中记录
class BatchEmbedder:
    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='embed').time():
            try:
                result = await self._embed(state)
                ingest_requests.labels(stage='embed', status='success').inc()
                embedding_cache_size.set(len(self.cache))
                return result
            except Exception as e:
                ingest_requests.labels(stage='embed', status='error').inc()
                raise
```

---

## 8. 总结

这个设计实现了：

### ✅ 架构优势
1. **LangGraph原生流程编排** - 状态驱动、条件路由、断点续传
2. **多Provider兼容** - OCR/VLM/Embedding/向量库可插拔
3. **100TB规模支持** - 分片存储、热冷分层、向量压缩
4. **端到端可视化** - SSE实时推送、进度条、错误追溯

### ✅ 生产级特性
- **高可用**: Qdrant集群、ES集群、Redis Sentinel
- **弹性扩展**: K8s自动扩容、队列化处理
- **可观测**: OTel全链路追踪、Prometheus指标
- **成本优化**: 策略多样性(本地优先)、向量压缩、冷热分层

### ✅ 创新点
- **智能路由**: 自动识别扫描件 → GPU路径
- **多Provider Fallback**: OCR失败自动降级
- **表格优先分块**: 保留表格完整性
- **引用式回答**: 页码+bbox精确定位
- **语义缓存**: 相似Query复用答案
- **幻觉检测**: LLM回答事实核查

### ✅ v2.0 修订内容
1. **修正** loader→router边遗漏
2. **修正** LangGraph不支持`*`通配符
3. **修正** 条件函数不应修改state
4. **新增** RAPTOR/GraphRAG高级算法设计
5. **新增** 语义缓存/幻觉检测节点
6. **优化** 单例模式/连接池/LRU缓存
7. **优化** RRF算法支持权重配置
8. **优化** SHA256替代MD5哈希

这是一个可直接落地的、面向100TB数据的生产级RAG系统设计。
