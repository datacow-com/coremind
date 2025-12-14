# Core 目录系统性审查报告

## 审查背景

**审查范围**: `/core` 目录全部模块
**设计基线**:

- `docs/tech/system-design.md` v2.0
- `docs/tech/large-pdf-processing.md`
- `docs/tech/implementation_plan.md`

**审查日期**: 2025-12-11

---

## 1. 执行摘要

### 1.1 总体评估

| 维度         | 评分 | 说明                                    |
| :----------- | :--: | :-------------------------------------- |
| 设计对齐度   | 75%  | 核心架构符合设计，部分细节偏差          |
| 多租户隔离   | 85%  | channel_id 已在关键路径实现，但存在遗漏 |
| 性能可扩展性 | 70%  | 单例/缓存已实现，大文件处理需加强       |
| 可配置性     | 80%  | StrategyConfig 完善，部分硬编码待清理   |
| 生产可用性   | 65%  | 质量闭环部分接入，观测性需增强          |

### 1.2 问题统计

| 优先级                | 数量 | 说明       |
| :-------------------- | :--: | :--------- |
| P0 (崩溃/越权/不可用) |  3   | 需立即修复 |
| P1 (设计对齐/质量)    |  8   | 本迭代修复 |
| P2 (增强/观测)        |  6   | 下迭代规划 |

---

## 2. P0 问题 (崩溃/越权/不可用)

### P0-1: GraphRAG Light 缺少 channel_id 字段导致多租户越权

**文件**: `core/algorithms/graphrag_light.py`
**函数**: `GraphLightState` TypedDict
**问题描述**:
`GraphLightState` 未定义 `channel_id` 字段，但 `light_collect` 调用 `collect_texts` 时，后者要求 `channel_id` 存在。这会导致：

1. 运行时 KeyError 或 ValueError
2. 若 channel_id 为空，可能导致跨租户数据泄露

**影响**:

- 多租户环境下 GraphRAG Light 无法运行
- 潜在数据越权风险

**修复思路**:

```python
class GraphLightState(TypedDict):
    kb_name: str
    channel_id: str  # 添加此字段
    language: str | None
    # ...
```

**验证步骤**:

1. 单测: 调用 `create_graphrag_light_graph()` 并传入不同 channel_id
2. 集成测试: 验证 channel A 的 GraphRAG 结果不包含 channel B 数据

---

### P0-2: RAPTOR Light 同样缺少 channel_id 字段

**文件**: `core/algorithms/raptor_light.py`
**函数**: `RaptorLightState` TypedDict
**问题描述**:
与 P0-1 相同，`RaptorLightState` 缺少 `channel_id` 字段。

**影响**: 同 P0-1

**修复思路**:

```python
class RaptorLightState(TypedDict):
    kb_name: str
    channel_id: str  # 添加此字段
    prompt: str
    # ...
```

**验证步骤**: 同 P0-1

---

### P0-3: MultimodalRetriever.search() 方法缺少 channel_id 参数

**文件**: `core/retrieval/multimodal/retriever.py`
**函数**: `MultimodalRetriever.search()`
**问题描述**:
直接调用 `search()` API 时未传递 `channel_id`，导致 `_search_kb()` 内部调用时 channel_id 为 None，可能导致：

1. 跨租户数据泄露
2. 与 `__call__` 方法行为不一致

**代码位置** (第 150-170 行):

```python
async def search(
    self,
    query: str | bytes,
    kb_names: list[str],
    modality: ModalityType = "text",
    top_k: int | None = None,
) -> list[MultimodalResult]:
    # 缺少 channel_id 参数
    for kb_name in kb_names:
        results = await self._search_kb(
            kb_name=kb_name,
            query_embedding=query_embedding,
            query_modality=modality,
            query_text=query if modality == "text" else "",
            # channel_id 未传递!
        )
```

**影响**:

- 直接调用 search() 的场景会绕过多租户隔离
- 生产环境数据安全风险

**修复思路**:

```python
async def search(
    self,
    query: str | bytes,
    kb_names: list[str],
    channel_id: str,  # 添加必需参数
    modality: ModalityType = "text",
    top_k: int | None = None,
) -> list[MultimodalResult]:
```

**验证步骤**:

1. 单测: 调用 search() 不传 channel_id 应抛出 TypeError
2. 集成测试: 验证不同 channel 的搜索结果隔离

---

## 3. P1 问题 (设计对齐/质量)

### P1-1: Ingestion Graph 缺少 error_handler 边连接

**文件**: `core/ingestion/graph.py`
**问题描述**:
`error_handler` 节点已注册，但没有从其他节点到 `error_handler` 的边。设计文档要求在 indexer 后添加错误检查路由。

**影响**: 错误处理节点永远不会被触发

**修复思路**:
在 `indexer` 后添加条件边:

```python
def _check_indexer_error(state: IngestState) -> str:
    if state.get("error_log") and state["retry_count"] < 3:
        return "error_handler"
    return "finalizer"

workflow.add_conditional_edges(
    "indexer",
    _check_indexer_error,
    {"error_handler": "error_handler", "finalizer": "finalizer"}
)
```

**验证步骤**:

1. 单测: 模拟 indexer 错误，验证 error_handler 被调用
2. 集成测试: 注入 Qdrant 连接失败，验证重试逻辑

---

### P1-2: ~~CpuTextParser/GpuVisionParser 未实现~~ ✅ 已验证完整

**文件**: `core/ingestion/nodes/parser/cpu_parser.py`, `core/ingestion/nodes/parser/gpu_parser.py`
**验证结果**:

- ✅ CpuTextParser 支持 PDF/Markdown/HTML/Email/DOCX/PPTX，含表格检测
- ✅ GpuVisionParser 实现了多 Provider (Qwen-VL, VolcEngine, DeepSeek, PaddleOCR)
- ✅ OCR fallback chain 已实现
- ✅ Rate limiting 和并发控制已实现
- ✅ 表格结构化输出为 Markdown 格式

**状态**: 无需修复，实现完整

---

### P1-3: Chunker 元数据缺少 heading_level 权重计算

**文件**: `core/ingestion/nodes/chunker.py`
**函数**: `_create_chunk()`
**问题描述**:
设计文档要求 `heading_level` 用于检索加权，但当前实现仅存储 heading_level，未在检索时使用。

**影响**: 标题内容无法获得更高 �� 索权重

**修复思路**:

1. Chunker 已正确存储 `heading_weight`
2. 需在 `HybridRetriever._rrf_fusion()` 中应用权重

**验证步骤**:

1. 单测: 验证 H1 标题 chunk 的 heading_weight > H3

---

### P1-4: Retriever RRF 融合未应用 metadata 权重

**文件**: `core/retrieval/nodes/retriever.py`
**函数**: `_rrf_fusion()`
**问题描述**:
RRF 融合仅使用排名计算分数，未考虑 chunk metadata 中的 `type_weight`, `position_weight`, `heading_weight`。

**影响**: 表格、标题等高价值内容无法获得更高排名

**修复思路**:

```python
def _rrf_fusion(self, vec_res, kw_res, k=60, channel_id=None):
    # ... existing code ...
    for doc_id, score in sorted_ids:
        chunk = self._to_chunk(docs[doc_id])
        # 应用 metadata 权重
        metadata = chunk.get("metadata", {})
        weight_multiplier = (
            metadata.get("type_weight", 1.0) *
            metadata.get("heading_weight", 1.0)
        )
        chunk["score"] = score * weight_multiplier
        fused_chunks.append(chunk)
```

**验证步骤**:

1. 单测: 验证 table 类型 chunk 分数高于同等 RRF 分数的 text chunk

---

### P1-5: SemanticCache 未在主检索图中正确接入

**文件**: `core/graph.py`
**问题描述**:
`semantic_cache` 节点已添加，但 `cache_result` 方法的调用方式不正确。`get_semantic_cache().cache_result` 返回的是方法引用，不是节点实例。

**代码位置** (第 180 行):

```python
graph.add_node("cache_result", get_semantic_cache().cache_result)
```

**影响**: cache_result 节点可能无法正确执行

**修复思路**:
创建包装类或使用 lambda:

```python
async def _cache_result_wrapper(state):
    cache = get_semantic_cache()
    return await cache.cache_result(state)

graph.add_node("cache_result", _cache_result_wrapper)
```

**验证步骤**:

1. 单测: 验证相同查询第二次命中缓存

---

### P1-6: LLMGateway 熔断状态未持久化

**文件**: `core/llm/gateway.py`
**问题描述**:
熔断状态 `_cb_state` 和 `_cb_cooldown` 存储在实例变量中，多实例部署时无法共享熔断状态。

**影响**: 分布式环境下熔断机制失效

**修复思路**:
使用 Redis 存储熔断状态，或改为类变量 + 进程内共享

**验证步骤**:

1. 集成测试: 模拟 LLM 连续失败，验证熔断触发

---

### P1-7: BatchEmbedder 缺少本地 LRU 缓存

**文件**: `core/ingestion/nodes/embedder.py`
**问题描述**:
设计文档要求 BatchEmbedder 实现本地 LRU 缓存避免重复 embedding，但当前实现未包含缓存逻辑。

**影响**: 重复文本会重复调用 embedding API，浪费资源

**修复思路**:

```python
from functools import lru_cache
import hashlib

class BatchEmbedder:
    def __init__(self):
        self._cache = {}  # 或使用 cachetools.LRUCache

    async def __call__(self, state):
        # 检查缓存
        for text in texts:
            cache_key = hashlib.sha256(text.encode()).hexdigest()[:32]
            if cache_key in self._cache:
                # 使用缓存
```

**验证步骤**:

1. 单测: 相同文本第二次 embed 应命中缓存

---

### P1-8: DualIndexer 图像索引缺少集合存在性检查

**文件**: `core/ingestion/nodes/indexer.py`
**函数**: `_index_images()`
**问题描述**:
在 upsert 图像向量前未检查集合是否存在，可能导致运行时错误。

**代码位置** (第 150 行):

```python
# 缺少: await vector_client.ensure_collection(collection_name, ...)
await vector_client.upsert(collection_name, points)
```

**影响**: 首次索引图像时可能失败

**修复思路**:

```python
await vector_client.ensure_collection(
    collection_name, dim=dim, enable_quantization=False
)
```

**验证步骤**:

1. 单测: 新 KB 首次索引图像应成功

---

## 4. P2 问题 (增强/观测)

### P2-1: 缺少关键节点的 OTel Span 属性

**文件**: 多个节点文件
**问题描述**:
虽然 `core/utils/monitor.py` 定义了 tracing 工具，但大多数节点未使用 `create_span` 或 `trace_async` 装饰器。

**影响**: 分布式追踪缺少详细信息

**修复思路**:
为关键节点添加 span:

```python
@trace_async("ingestion.chunker", {"mode": "layout_aware"})
async def __call__(self, state):
    with create_span("chunker.process", {"chunk_count": len(chunks)}):
        # ...
```

---

### P2-2: 缺少 RAPTOR/GraphRAG 处理进度指标

**文件**: `core/algorithms/raptor_deep.py`, `core/algorithms/graphrag_deep.py`
**问题描述**:
算法处理过程缺少进度指标上报，无法监控大规模处理任务。

**修复思路**:
使用 `algorithm_duration` 和 `algorithm_chunks_processed` 指标

---

### P2-3: HallucinationChecker 结果未影响最终输出

**文件**: `core/graph.py`
**问题描述**:
当前实现在检测到幻觉时仅添加警告前缀，未提供降级策略（如返回"无法确认"）。

**修复思路**:
添加配置项控制幻觉检测后的行为

---

### P2-4: 缺少 Embedding 批处理性能指标

**文件**: `core/ingestion/nodes/embedder.py`
**问题描述**:
未记录每批 embedding 的耗时和吞吐量。

**修复思路**:
添加 `embedding_batch_duration` Histogram

---

### P2-5: StrategyConfig 缺少 reranker 配置验证

**文件**: `core/state.py`
**问题描述**:
`StrategyConfig` 未定义 `reranker_provider`, `reranker_model` 等字段，导致配置分散。

**修复思路**:
添加 RerankerConfig 嵌套类

---

### P2-6: 缺少 KB 配置热更新机制

**文件**: `core/storage/kb_config.py`
**问题描述**:
KB 配置加载后未提供热更新机制，配置变更需重启服务。

**修复思路**:
添加配置版本检查和自动重载

---

## 5. 修复优先级清单

### 立即修复 (P0)

1. [ ] P0-1: GraphRAG Light 添加 channel_id
2. [ ] P0-2: RAPTOR Light 添加 channel_id
3. [ ] P0-3: MultimodalRetriever.search() 添加 channel_id 参数

### 本迭代修复 (P1)

4. [ ] P1-1: Ingestion Graph 添加 error_handler 边
5. [x] P1-2: ~~验证 Parser 实现完整性~~ ✅ 已验证完整
6. [ ] P1-3: 验证 heading_level 权重存储
7. [ ] P1-4: RRF 融合应用 metadata 权重
8. [ ] P1-5: 修复 SemanticCache 节点接入
9. [ ] P1-6: LLMGateway 熔断状态共享
10. [ ] P1-7: BatchEmbedder 添加 LRU 缓存
11. [ ] P1-8: DualIndexer 图像集合检查

### 下迭代规划 (P2)

12. [ ] P2-1: 添加 OTel Span 属性
13. [ ] P2-2: RAPTOR/GraphRAG 进度指标
14. [ ] P2-3: HallucinationChecker 降级策略
15. [ ] P2-4: Embedding 批处理指标
16. [ ] P2-5: StrategyConfig 完善
17. [ ] P2-6: KB 配置热更新

---

## 6. 验证计划

### 6.1 单元测试

```bash
# P0 多租户隔离测试
pytest tests/core/test_algorithms.py -k "channel_id"
pytest tests/core/test_multimodal_retriever.py -k "channel_isolation"

# P1 功能测试
pytest tests/core/test_ingestion_graph.py -k "error_handler"
pytest tests/core/test_retriever.py -k "rrf_weights"
pytest tests/core/test_semantic_cache.py
```

### 6.2 集成测试

```bash
# 端到端多租户测试
python scripts/e2e_multi_tenant.py --channels A,B --verify-isolation

# 大文件处理测试
python scripts/e2e_large_pdf.py --file-size 200MB --verify-streaming
```

### 6.3 性能测试

```bash
# Embedding 批处理性能
python scripts/benchmark_embedding.py --batch-sizes 32,64,128

# 检索延迟测试
python scripts/benchmark_retrieval.py --concurrent 10 --queries 1000
```

---

## 7. 附录：文件引用索引

| 文件路径                                 | 审查状态 | 主要问题   |
| :--------------------------------------- | :------: | :--------- |
| `core/state.py`                          |    ✅    | P2-5       |
| `core/graph.py`                          |    ✅    | P1-5       |
| `core/ingestion/graph.py`                |    ✅    | P1-1       |
| `core/ingestion/nodes/chunker.py`        |    ✅    | P1-3       |
| `core/ingestion/nodes/embedder.py`       |    ✅    | P1-7, P2-4 |
| `core/ingestion/nodes/indexer.py`        |    ✅    | P1-8       |
| `core/retrieval/nodes/retriever.py`      |    ✅    | P1-4       |
| `core/retrieval/nodes/semantic_cache.py` |    ✅    | P1-5       |
| `core/retrieval/multimodal/retriever.py` |    ✅    | P0-3       |
| `core/algorithms/graphrag_light.py`      |    ✅    | P0-1       |
| `core/algorithms/raptor_light.py`        |    ✅    | P0-2       |
| `core/algorithms/graphrag_deep.py`       |    ✅    | -          |
| `core/algorithms/raptor_deep.py`         |    ✅    | -          |
| `core/llm/gateway.py`                    |    ✅    | P1-6       |
| `core/utils/monitor.py`                  |    ✅    | P2-1       |
