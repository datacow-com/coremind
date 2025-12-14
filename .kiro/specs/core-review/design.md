# Core 审查问题修复设计

## 1. 概述

本设计文档描述了 `/core` 目录审查中发现的 P0/P1 问题的修复方案。

### 1.1 修复范围

| 优先级 | 问题数 | 修复策略           |
| :----- | :----: | :----------------- |
| P0     |   3    | 立即修复，阻塞发布 |
| P1     |   7    | 本迭代修复         |
| P2     |   6    | 下迭代规划         |

### 1.2 设计原则

1. **最小改动原则**: 仅修改必要代码，避免引入新风险
2. **向后兼容**: 保持现有 API 签名兼容
3. **测试驱动**: 每个修复必须有对应测试用例
4. **渐进式**: P0 → P1 → P2 顺序修复

---

## 2. P0 修复设计

### 2.1 P0-1 & P0-2: Algorithm Light 版本添加 channel_id

#### 2.1.1 问题分析

```
GraphLightState / RaptorLightState
    ↓ 调用
collect_texts() (from deep version)
    ↓ 要求
channel_id 字段存在
    ↓ 当前
KeyError 或 ValueError
```

#### 2.1.2 修复方案

**文件**: `core/algorithms/graphrag_light.py`

```python
class GraphLightState(TypedDict):
    kb_name: str
    channel_id: str  # 新增: 多租户隔离必需
    language: str | None
    entity_types: list[str] | None
    chunks: list[str]
    graph: dict[str, Any]
    meta: dict[str, Any]
```

**文件**: `core/algorithms/raptor_light.py`

```python
class RaptorLightState(TypedDict):
    kb_name: str
    channel_id: str  # 新增: 多租户隔离必需
    prompt: str
    max_token: int
    threshold: float
    max_cluster: int
    random_seed: int
    chunks: list[str]
    layers: list[list[int]]
    summaries: list[dict[str, Any]]
    meta: dict[str, Any]
```

#### 2.1.3 影响分析

- **API 变更**: 调用方需传入 `channel_id`
- **向后兼容**: 无，但这是安全修复，必须强制
- **测试**: 新增 `test_algorithm_channel_isolation.py`

---

### 2.2 P0-3: MultimodalRetriever.search() 添加 channel_id

#### 2.2.1 问题分析

```
search() 方法
    ↓ 调用
_search_kb(channel_id=None)
    ↓ 导致
跨租户数据泄露
```

#### 2.2.2 修复方案

**文件**: `core/retrieval/multimodal/retriever.py`

```python
async def search(
    self,
    query: str | bytes,
    kb_names: list[str],
    channel_id: str,  # 新增: 必需参数
    modality: ModalityType = "text",
    top_k: int | None = None,
) -> list[MultimodalResult]:
    """
    Direct search API for multimodal queries.

    Args:
        query: Text string or image bytes
        kb_names: Knowledge bases to search
        channel_id: Required channel identifier for tenant isolation
        modality: Query modality type
        top_k: Number of results to return

    Returns:
        List of MultimodalResult
    """
    k = top_k or self.top_k

    # Generate query embedding
    query_embedding = await self.embedder.embed(query, modality)

    all_results = []
    for kb_name in kb_names:
        results = await self._search_kb(
            kb_name=kb_name,
            query_embedding=query_embedding,
            query_modality=modality,
            query_text=query if modality == "text" else "",
            channel_id=channel_id,  # 传递 channel_id
        )
        all_results.extend(results)

    # Rank and return top k
    ranked = self._rank_results(all_results, modality)
    return ranked[:k]
```

#### 2.2.3 影响分析

- **API 变更**: `search()` 签名变更，`channel_id` 为必需参数
- **向后兼容**: 破坏性变更，但安全优先
- **测试**: 更新 `test_multimodal_retriever.py`

---

## 3. P1 修复设计

### 3.1 P1-1: Ingestion Graph 添加 error_handler 边

#### 3.1.1 修复方案

**文件**: `core/ingestion/graph.py`

```python
def _check_indexer_error(state: IngestState) -> str:
    """Check if indexer had errors and decide next step."""
    error_log = state.get("error_log", [])
    retry_count = state.get("retry_count", 0)

    # Check for indexer-specific errors
    indexer_errors = [e for e in error_log if e.get("stage") == "indexer"]

    if indexer_errors and retry_count < 3:
        return "error_handler"
    return "finalizer"


def create_ingest_graph():
    # ... existing code ...

    # 修改: indexer 后添加条件边
    workflow.add_conditional_edges(
        "indexer",
        _check_indexer_error,
        {
            "error_handler": "error_handler",
            "finalizer": "finalizer"
        }
    )

    # 移除原有的直接边
    # workflow.add_edge("indexer", "finalizer")  # 删除此行
```

---

### 3.2 P1-4: RRF 融合应用 metadata 权重

#### 3.2.1 修复方案

**文件**: `core/retrieval/nodes/retriever.py`

```python
def _rrf_fusion(
    self, vec_res: list[dict], kw_res: list[dict], k: int = 60,
    channel_id: str | None = None
) -> list[RetrievedChunk]:
    """
    RRF (Reciprocal Rank Fusion) with metadata weight boosting.
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    # P0 Fix: Filter by channel_id
    if channel_id:
        vec_res = [r for r in vec_res if self._validate_channel(r, channel_id)]
        kw_res = [r for r in kw_res if self._validate_channel(r, channel_id)]

    # Rank Vector
    vec_res.sort(key=lambda x: x.get("score", 0), reverse=True)
    for rank, item in enumerate(vec_res):
        doc_id = str(item["id"])
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        docs[doc_id] = item

    # Rank Keyword
    kw_res.sort(key=lambda x: x.get("score", 0), reverse=True)
    for rank, item in enumerate(kw_res):
        doc_id = str(item["id"])
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        if doc_id not in docs:
            docs[doc_id] = item

    # Sort by RRF score
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    fused_chunks = []
    for doc_id, rrf_score in sorted_ids:
        chunk = self._to_chunk(docs[doc_id])

        # P1 Fix: Apply metadata weights
        metadata = chunk.get("metadata", {})
        type_weight = metadata.get("type_weight", 1.0)
        heading_weight = metadata.get("heading_weight", 1.0)
        position_weight = metadata.get("position_weight", 1.0)

        # Combined weight multiplier
        weight_multiplier = (
            type_weight * 0.4 +      # 表格/标题权重
            heading_weight * 0.3 +   # 标题层级权重
            position_weight * 0.3    # 位置权重
        )

        chunk["score"] = rrf_score * weight_multiplier
        fused_chunks.append(chunk)

    return fused_chunks

def _validate_channel(self, result: dict, channel_id: str) -> bool:
    """Validate result belongs to specified channel."""
    result_channel = (
        result.get("metadata", {}).get("channel_id") or
        result.get("channel_id")
    )
    # Allow legacy data without channel
    if not result_channel:
        return True
    return result_channel == channel_id
```

---

### 3.3 P1-5: SemanticCache 节点接入修复

#### 3.3.1 修复方案

**文件**: `core/graph.py`

```python
# 创建包装函数
async def _semantic_cache_check(state: RetrievalState) -> RetrievalState:
    """Wrapper for semantic cache check."""
    cache = get_semantic_cache()
    return await cache(state)


async def _semantic_cache_store(state: RetrievalState) -> RetrievalState:
    """Wrapper for semantic cache store."""
    cache = get_semantic_cache()
    return await cache.cache_result(state)


def create_graph():
    # ...

    # 使用包装函数而非方法引用
    graph.add_node("semantic_cache", _semantic_cache_check)
    graph.add_node("cache_result", _semantic_cache_store)

    # ...
```

---

### 3.4 P1-6: LLMGateway 熔断状态共享

#### 3.4.1 修复方案

**文件**: `core/llm/gateway.py`

```python
import threading

class LLMGateway:
    """
    DB 驱动的 LLM 网关：统一模型选取、熔断/降级、用量记录。

    P1 Fix: 使用类变量共享熔断状态，支持进程内多实例共享。
    """

    # 类变量: 进程内共享熔断状态
    _cb_state_lock = threading.Lock()
    _cb_state: dict[str, list[float]] = {}
    _cb_cooldown: dict[str, float] = {}

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.default_provider_name = provider or settings.llm_provider or "openai"
        self.default_model_name = model
        self.http_timeout = float(os.environ.get("LLM_HTTP_TIMEOUT", "60"))
        self.fallback_models: list[str] = []

    def _cb_allowed(self, provider: str) -> bool:
        """Check if provider is allowed (not in cooldown)."""
        with LLMGateway._cb_state_lock:
            now = time.time()
            next_allow = LLMGateway._cb_cooldown.get(provider)
            if next_allow and now < next_allow:
                return False
            return True

    def _cb_on_fail(self, provider: str) -> None:
        """Record failure for circuit breaker."""
        with LLMGateway._cb_state_lock:
            now = time.time()
            window = 60.0
            max_fail = 3
            fails = [t for t in LLMGateway._cb_state.get(provider, []) if now - t <= window]
            fails.append(now)
            LLMGateway._cb_state[provider] = fails
            if len(fails) >= max_fail:
                LLMGateway._cb_cooldown[provider] = now + 30.0

    def _cb_on_success(self, provider: str) -> None:
        """Clear failure state on success."""
        with LLMGateway._cb_state_lock:
            LLMGateway._cb_state.pop(provider, None)
            LLMGateway._cb_cooldown.pop(provider, None)
```

---

### 3.5 P1-7: BatchEmbedder 添加 LRU 缓存

#### 3.5.1 修复方案

**文件**: `core/ingestion/nodes/embedder.py`

```python
import hashlib
from cachetools import LRUCache

class BatchEmbedder:
    """
    Batch embedder with LRU caching.

    P1 Fix: Added LRU cache to avoid redundant embedding calls.
    """

    # 类级别缓存，进程内共享
    _embedding_cache: LRUCache = LRUCache(maxsize=10000)

    def __init__(self):
        self._semaphore: asyncio.Semaphore | None = None

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='embedder').time():
            cfg = state['strategy_config']
            model_name = cfg.get('embedding_model', 'BAAI/bge-m3')
            batch_size = cfg.get('embedding_batch_size', 64)

            chunks = state['chunks']
            if not chunks:
                state['vectors'] = []
                state['processing_stage'] = 'index'
                return state

            texts = [c['content'] for c in chunks]
            embedder = get_embedder(model_name=model_name)

            vectors = []
            texts_to_embed = []
            text_indices = []

            # Check cache first
            for i, text in enumerate(texts):
                cache_key = self._cache_key(text, model_name)
                cached = BatchEmbedder._embedding_cache.get(cache_key)
                if cached is not None:
                    vectors.append((i, cached))
                else:
                    texts_to_embed.append(text)
                    text_indices.append(i)

            # Embed uncached texts
            if texts_to_embed:
                if asyncio.iscoroutinefunction(embedder.embed_batch):
                    new_vectors = await embedder.embed_batch(texts_to_embed)
                else:
                    new_vectors = await asyncio.to_thread(embedder.embed_batch, texts_to_embed)

                # Cache and collect results
                for idx, text, vec in zip(text_indices, texts_to_embed, new_vectors):
                    cache_key = self._cache_key(text, model_name)
                    vec_list = vec.tolist() if hasattr(vec, 'tolist') else list(vec)
                    BatchEmbedder._embedding_cache[cache_key] = vec_list
                    vectors.append((idx, vec_list))

            # Sort by original index
            vectors.sort(key=lambda x: x[0])
            state['vectors'] = [v for _, v in vectors]
            state['processing_stage'] = 'index'

            return state

    def _cache_key(self, text: str, model_name: str) -> str:
        """Generate cache key for text + model."""
        content = f"{model_name}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
```

---

### 3.6 P1-8: DualIndexer 图像集合检查

#### 3.6.1 修复方案

**文件**: `core/ingestion/nodes/indexer.py`

```python
async def _index_images(
    self,
    state: IngestState,
    images: list[dict[str, Any]],
    vector_client: Any,
    kb_name: str,
    version: int,
    channel_id: str | None,
    dim: int,
) -> None:
    """Index image embeddings to dedicated collection."""
    # Collection name for images
    if channel_id:
        collection_name = f"ch_{channel_id}_kb_{kb_name}_v{version}_images"
    else:
        collection_name = f"kb_{kb_name}_v{version}_images"

    # P1 Fix: Ensure image collection exists before upsert
    await vector_client.ensure_collection(
        collection_name,
        dim=dim,
        enable_quantization=False  # Images typically don't benefit from quantization
    )

    # ... rest of the method unchanged ...
```

---

## 4. 测试策略

### 4.1 单元测试

| 测试文件                       | 覆盖问题   | 测试用例                  |
| :----------------------------- | :--------- | :------------------------ |
| `test_algorithm_channel.py`    | P0-1, P0-2 | channel_id 必需性、隔离性 |
| `test_multimodal_retriever.py` | P0-3       | search() 签名、隔离性     |
| `test_ingestion_graph.py`      | P1-1       | error_handler 触发        |
| `test_retriever_weights.py`    | P1-4       | metadata 权重应用         |
| `test_semantic_cache.py`       | P1-5       | 缓存命中/未命中           |
| `test_llm_gateway.py`          | P1-6       | 熔断状态共享              |
| `test_embedder_cache.py`       | P1-7       | LRU 缓存命中              |
| `test_indexer_multimodal.py`   | P1-8       | 图像集合创建              |

### 4.2 集成测试

```bash
# 多租户隔离端到端测试
python scripts/e2e_multi_tenant.py \
    --channels A,B \
    --verify-isolation \
    --test-algorithms raptor,graphrag

# 错误恢复测试
python scripts/e2e_error_recovery.py \
    --inject-error indexer \
    --verify-retry
```

---

## 5. 部署注意事项

### 5.1 破坏性变更

| 变更                 | 影响         | 迁移方案             |
| :------------------- | :----------- | :------------------- |
| `search()` 签名变更  | 调用方需更新 | 添加 channel_id 参数 |
| Algorithm State 变更 | 调用方需更新 | 添加 channel_id 参数 |

### 5.2 依赖更新

```txt
# requirements.txt 新增
cachetools>=5.0.0  # P1-7 LRU 缓存
```

### 5.3 配置变更

无新增配置项。

---

## 6. 风险评估

| 风险                       | 概率 | 影响 | 缓解措施               |
| :------------------------- | :--: | :--: | :--------------------- |
| API 破坏性变更导致调用失败 |  中  |  高  | 发布前通知、版本号升级 |
| 缓存导致内存增长           |  低  |  中  | LRU 限制 maxsize       |
| 熔断状态竞争条件           |  低  |  低  | 使用 threading.Lock    |
