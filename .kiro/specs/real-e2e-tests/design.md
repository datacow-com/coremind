# Design Document: Real Environment E2E Tests

## Overview

本设计文档定义了 OmniRAG 核心模块的真实环境端到端（E2E）与集成测试架构。测试将使用 `tests/core/docs` 目录下的真实文档，连接 docker-compose 启动的真实依赖服务，验证系统在生产级条件下的正确性。

### 设计原则

1. **真实依赖优先**: 使用 docker-compose 启动的 Qdrant、Elasticsearch、MinIO、Redis，禁止 mock
2. **资源感知**: 适配 Apple M4 Pro 24G 内存限制，避免 OOM
3. **多租户隔离**: 每个测试使用独立 channel_id，验证跨租户隔离
4. **优雅降级**: 缺少 GPU/模型/外网时使用 pytest.importorskip 或 skip
5. **资源清理**: 测试后清理 collections、indexes、MinIO 对象、临时文件

### 测试文件选择

从 `tests/core/docs` 选择以下代表性文件：

| 文件类型     | 文件路径                    | 用途                   |
| ------------ | --------------------------- | ---------------------- |
| 大 PDF       | `地方导游基础知识.pdf`      | 流式摄取、内存管理     |
| 表格 PDF     | `Slang Rules...pdf`         | 表格解析、layout_aware |
| 图文混排 PDF | `2010_图说十二月花神.pdf`   | 图像提取、OCR          |
| PPTX         | `儿童节76.pptx`             | 多媒体解析             |
| Word 批量    | `word模板/*.docx` (选 5 个) | 批量处理               |
| ZIP 包       | 动态创建测试 ZIP            | ZIP 炸弹防护           |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Test Infrastructure                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Qdrant    │  │Elasticsearch│  │    MinIO    │  │    Redis    │ │
│  │  :3508      │  │   :3507     │  │   :3510     │  │   :3509     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Test Fixtures                               │
├─────────────────────────────────────────────────────────────────────┤
│  conftest.py:                                                       │
│  - real_qdrant_client: QdrantClient(host=localhost, port=3508)     │
│  - real_es_client: Elasticsearch(hosts=[localhost:3507])           │
│  - real_minio_client: Minio(endpoint=localhost:3510)               │
│  - real_redis_client: Redis(host=localhost, port=3509)             │
│  - test_channel_a: "test_channel_a_{uuid}"                         │
│  - test_channel_b: "test_channel_b_{uuid}"                         │
│  - cleanup_fixture: 测试后清理所有资源                              │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Test Modules                                │
├─────────────────────────────────────────────────────────────────────┤
│  tests/core/ingestion/test_ingest_real_docs.py                     │
│  tests/core/retrieval/test_retrieval_real_docs.py                  │
│  tests/core/storage/test_storage_real_docs.py                      │
│  tests/core/state/test_state_real.py                               │
│  tests/core/algorithms/test_algorithms_real_docs.py                │
└─────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Test Fixtures (conftest.py)

```python
# tests/core/conftest_real.py

@pytest.fixture(scope="session")
def real_qdrant_client():
    """真实 Qdrant 客户端，从环境变量读取端点"""
    from qdrant_client import QdrantClient
    host = os.environ.get("QDRANT_HOST", "localhost")
    port = int(os.environ.get("QDRANT_PORT", "3508"))
    client = QdrantClient(host=host, port=port)
    yield client
    # Cleanup handled by cleanup_fixture

@pytest.fixture(scope="session")
def real_es_client():
    """真实 Elasticsearch 客户端"""
    from elasticsearch import Elasticsearch
    url = os.environ.get("ELASTICSEARCH_URL", "http://localhost:3507")
    client = Elasticsearch(hosts=[url])
    yield client

@pytest.fixture(scope="function")
def test_channel_a():
    """生成唯一 channel_id 用于测试隔离"""
    return f"test_channel_a_{uuid.uuid4().hex[:8]}"

@pytest.fixture(scope="function")
def test_channel_b():
    """第二个 channel 用于跨租户测试"""
    return f"test_channel_b_{uuid.uuid4().hex[:8]}"

@pytest.fixture(autouse=True)
def cleanup_fixture(real_qdrant_client, real_es_client, test_channel_a, test_channel_b):
    """测试后清理所有创建的资源"""
    yield
    # Cleanup collections and indexes
    for channel in [test_channel_a, test_channel_b]:
        # Delete Qdrant collections
        # Delete ES indexes
        # Delete MinIO objects
        # Clean temp files
```

### 2. Ingestion Test Module

```python
# tests/core/ingestion/test_ingest_real_docs.py

class TestIngestRealDocs:
    """真实文档摄取测试"""

    @pytest.mark.asyncio
    async def test_large_pdf_lazy_load(self, test_channel_a, real_qdrant_client):
        """测试大 PDF 流式摄取"""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="GPU not available")
    async def test_gpu_parser_routing(self, test_channel_a):
        """测试 GPU 解析器路由"""

    async def test_zip_bomb_protection(self, test_channel_a):
        """测试 ZIP 炸弹防护"""

    @pytest.mark.parametrize("strategy", ["fixed", "semantic", "layout_aware", "table_first"])
    async def test_chunking_strategies(self, test_channel_a, strategy):
        """测试不同分块策略"""
```

### 3. Retrieval Test Module

```python
# tests/core/retrieval/test_retrieval_real_docs.py

class TestRetrievalRealDocs:
    """真实文档检索测试"""

    @pytest.fixture(autouse=True)
    async def setup_indexed_docs(self, test_channel_a, real_qdrant_client):
        """预先索引测试文档"""

    async def test_semantic_cache_miss(self, test_channel_a):
        """测试语义缓存未命中"""

    async def test_semantic_cache_hit(self, test_channel_a):
        """测试语义缓存命中"""

    async def test_hybrid_retrieval_rrf(self, test_channel_a):
        """测试混合检索 RRF 融合"""

    async def test_cross_tenant_isolation(self, test_channel_a, test_channel_b):
        """测试跨租户隔离"""
```

### 4. Storage Test Module

```python
# tests/core/storage/test_storage_real_docs.py

class TestStorageRealDocs:
    """真实存储层测试"""

    async def test_channel_naming_convention(self, test_channel_a):
        """测试 channel 命名规范"""

    async def test_dual_write_consistency(self, test_channel_a):
        """测试向量/关键词双写一致性"""

    async def test_dimension_mismatch_error(self, test_channel_a):
        """测试维度不匹配错误"""
```

## Data Models

### Test State Tracking

```python
@dataclass
class TestExecutionState:
    """测试执行状态追踪"""
    channel_id: str
    created_collections: list[str]
    created_indexes: list[str]
    uploaded_objects: list[str]
    temp_files: list[Path]
    start_time: float
    memory_baseline: int
```

### Test Document Metadata

```python
@dataclass
class TestDocument:
    """测试文档元数据"""
    path: Path
    file_type: str
    expected_chunks_min: int
    expected_chunks_max: int
    has_tables: bool
    has_images: bool
    size_bytes: int
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

Based on the prework analysis, the following correctness properties are defined:

### Property 1: Large File Lazy Loading

_For any_ PDF file larger than 5MB from tests/core/docs, the ingestion pipeline should complete processing within 120 seconds without exceeding 2x baseline memory usage.
**Validates: Requirements 1.1**

### Property 2: ZIP Bomb Protection

_For any_ ZIP file containing more than 100 files or exceeding 500MB uncompressed size, the ingestion pipeline should reject the file and record "zip_bomb_protection" in error_log.
**Validates: Requirements 1.3**

### Property 3: Mixed Content Extraction

_For any_ PDF containing both tables and images, the ingestion pipeline should produce chunks with appropriate block_type metadata ("table" or "image") for each content type.
**Validates: Requirements 1.4**

### Property 4: Chunking Strategy Differentiation

_For any_ document processed with different chunking strategies (fixed, semantic, layout_aware, table_first), the resulting chunk counts should differ, and table_first strategy should preserve table integrity when preserve_tables is enabled.
**Validates: Requirements 1.5**

### Property 5: Dual-Write Consistency

_For any_ document successfully ingested, the document count in Qdrant vector store should equal the document count in Elasticsearch keyword store.
**Validates: Requirements 1.6, 3.3**

### Property 6: Temporary File Cleanup

_For any_ completed ingestion (success or failure), the temporary processing directory should contain zero files after finalization.
**Validates: Requirements 1.7**

### Property 7: Channel-Prefixed Storage

_For any_ document indexed for channel*A, all vectors should be stored in collections prefixed with "channel_A*" and all keywords in indexes prefixed with "channel*A*".
**Validates: Requirements 1.8**

### Property 8: Semantic Cache Miss Pipeline

_For any_ query executed for the first time (no cache entry exists), the retrieval pipeline should execute retriever, reranker, and generator nodes in sequence.
**Validates: Requirements 2.1**

### Property 9: Semantic Cache Hit Bypass

_For any_ query executed within cache TTL after a previous identical query, the retrieval pipeline should skip retriever and reranker nodes and return cached results.
**Validates: Requirements 2.2**

### Property 10: Hybrid Retrieval RRF Fusion

_For any_ query with hybrid retrieval enabled, the fused_results should contain results from both Qdrant (vector_results) and Elasticsearch (keyword_results) combined using RRF algorithm.
**Validates: Requirements 2.3**

### Property 11: Reranker Score Ordering

_For any_ query with CrossEncoder reranker enabled, the reranked_results should be ordered by rerank_score in descending order.
**Validates: Requirements 2.4**

### Property 12: Hallucination Check Confidence Impact

_For any_ generated answer where hallucination_score exceeds the configured threshold, the confidence score should be reduced and final_answer should contain a warning prefix.
**Validates: Requirements 2.6**

### Property 13: Cross-Tenant Query Isolation

_For any_ query executed against channel_A, the returned results should contain zero chunks from channel_B, regardless of what documents are indexed in channel_B.
**Validates: Requirements 2.7, 3.6, 5.6**

### Property 14: Citation Required Fields

_For any_ successful retrieval with results, each citation should contain non-null doc_id, page_num, and content fields.
**Validates: Requirements 2.8**

### Property 15: Channel Naming Convention

_For any_ channel*id, the generated collection name should follow the pattern "{channel_id}*{base_name}" where base_name is the configured collection name.
**Validates: Requirements 3.1**

### Property 16: Pagination Stability

_For any_ paginated query across multiple scroll requests, the union of all page results should be consistent and contain no duplicates.
**Validates: Requirements 3.2, 5.5**

### Property 17: Flat Config Override

_For any_ StrategyConfig with both flat fields (chunking_mode) and nested fields (chunking.mode), the effective value should be the flat field value.
**Validates: Requirements 4.1**

### Property 18: Falsy Value Handling

_For any_ StrategyConfig with falsy values (0 for chunk_overlap, False for preserve_tables), the effective properties should return the falsy value, not the default.
**Validates: Requirements 4.2**

### Property 19: Config Serialization Round-Trip

_For any_ StrategyConfig instance, serializing to JSON and deserializing should produce an equivalent configuration object.
**Validates: Requirements 4.4**

### Property 20: RAPTOR Clustered Summaries

_For any_ set of indexed documents, raptor_light or raptor_deep should return clustered summaries with pagination support (page, page_size, total parameters).
**Validates: Requirements 5.1**

### Property 21: GraphRAG Entity-Relation Graphs

_For any_ set of indexed documents in channel_A, graphrag_light or graphrag_deep should build entity-relation graphs containing only entities from channel_A documents.
**Validates: Requirements 5.2**

### Property 22: MindMap Hierarchical Structure

_For any_ set of indexed chunks, mindmap_light should generate a hierarchical topic structure with parent-child relationships.
**Validates: Requirements 5.3**

## Error Handling

### 依赖服务不可用

```python
@pytest.fixture(scope="session")
def check_services():
    """检查所有依赖服务是否可用"""
    services = {
        "qdrant": ("localhost", 3508),
        "elasticsearch": ("localhost", 3507),
        "minio": ("localhost", 3510),
        "redis": ("localhost", 3509),
    }
    unavailable = []
    for name, (host, port) in services.items():
        if not is_port_open(host, port):
            unavailable.append(name)
    if unavailable:
        pytest.skip(f"Services unavailable: {unavailable}. Run: docker-compose up -d")
```

### GPU 不可用

```python
def skip_if_no_gpu(reason="GPU not available"):
    """GPU 不可用时跳过测试"""
    try:
        import torch
        if not torch.cuda.is_available():
            return pytest.mark.skip(reason=reason)
    except ImportError:
        return pytest.mark.skip(reason="torch not installed")
    return lambda f: f
```

### 外网不可用

```python
async def check_web_search_available():
    """检查外网搜索是否可用"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get("https://duckduckgo.com")
        return True
    except Exception:
        return False
```

### 模型缺失

```python
def require_model(model_name: str):
    """检查模型是否存在"""
    model_path = Path(f"models/{model_name}")
    if not model_path.exists():
        pytest.importorskip(model_name, reason=f"Model {model_name} not present at {model_path}")
```

## Testing Strategy

### 双重测试方法

本测试套件采用单元测试和属性测试相结合的方法：

1. **单元测试**: 验证特定示例和边界情况
2. **属性测试**: 使用 Hypothesis 验证跨所有输入的通用属性

### 属性测试框架

使用 **Hypothesis** 作为 Python 属性测试库：

```python
from hypothesis import given, strategies as st, settings

@given(st.text(min_size=1, max_size=100))
@settings(max_examples=100)
def test_channel_naming_property(channel_id):
    """Property 15: Channel naming convention"""
    # **Feature: real-e2e-tests, Property 15: Channel Naming Convention**
    collection_name = generate_collection_name(channel_id, "chunks")
    assert collection_name.startswith(f"{channel_id}_")
```

### 测试配置

```python
# pytest.ini additions
[pytest]
markers =
    real_e2e: marks tests as real E2E tests (require docker-compose services)
    slow: marks tests as slow (>30s)
    gpu: marks tests as requiring GPU

# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "real_e2e: real E2E tests")
    config.addinivalue_line("markers", "slow: slow tests")
    config.addinivalue_line("markers", "gpu: GPU required tests")
```

### 并发控制

```bash
# 避免 OOM，限制并发
pytest tests/core -q -n 4 --dist loadscope

# 按模块分组，避免资源竞争
pytest tests/core/ingestion -q -n 2
pytest tests/core/retrieval -q -n 2
```

### 资源清理策略

```python
@pytest.fixture(autouse=True, scope="function")
async def cleanup_after_test(real_qdrant_client, real_es_client, test_channel_a, test_channel_b):
    """每个测试后清理资源"""
    yield

    # 1. 删除 Qdrant collections
    for channel in [test_channel_a, test_channel_b]:
        collections = real_qdrant_client.get_collections().collections
        for col in collections:
            if col.name.startswith(channel):
                real_qdrant_client.delete_collection(col.name)

    # 2. 删除 ES indexes
    for channel in [test_channel_a, test_channel_b]:
        indices = real_es_client.indices.get(index=f"{channel}_*")
        for index in indices:
            real_es_client.indices.delete(index=index)

    # 3. 清理临时文件
    tmp_dir = Path("uploads/tmp")
    for f in tmp_dir.glob("*"):
        f.unlink()
```

### 执行命令

```bash
# 启动依赖服务
docker-compose up -d qdrant elasticsearch minio redis

# 运行全部真实 E2E 测试
pytest tests/core -q --maxfail=1 --disable-warnings -m real_e2e

# 并发执行（可选，注意内存）
pytest tests/core -q -n 4 --dist loadscope -m real_e2e

# 聚焦 ingestion
pytest tests/core/ingestion/test_ingest_real_docs.py -q -k "pdf or zip"

# 聚焦 retrieval
pytest tests/core/retrieval/test_retrieval_real_docs.py -q -k "cache or hybrid"

# 聚焦 storage
pytest tests/core/storage/test_storage_real_docs.py -q -k "channel or dual"

# 跳过慢测试
pytest tests/core -q -m "real_e2e and not slow"
```

### 属性测试标注规范

每个属性测试必须包含以下注释格式：

```python
def test_property_name(self):
    """
    **Feature: real-e2e-tests, Property N: Property Name**
    **Validates: Requirements X.Y**
    """
```
