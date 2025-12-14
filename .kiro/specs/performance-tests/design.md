# Design Document: 性能测试套件

## Overview

本设计文档定义了 OmniRAG 系统的性能测试方案，覆盖大文件 ingest、并发控制、reranker 非阻塞、以及多种缓存的性能对比测试。测试使用 pytest 和 pytest-benchmark 进行基准测试，使用 hypothesis 进行属性测试。

## Architecture

```
tests/core/performance/
├── conftest.py                    # 共享 fixtures 和性能测试工具
├── test_large_file_ingest.py      # 大文件 ingest 内存/耗时测试
├── test_concurrency_control.py    # Semaphore 并发控制测试
├── test_reranker_nonblocking.py   # Reranker async 非阻塞测试
├── test_cache_comparison.py       # 缓存性能对比测试
└── utils/
    ├── fake_blob_store.py         # Fake blob_store 实现
    ├── memory_tracker.py          # 内存追踪工具
    └── metrics_collector.py       # 性能指标收集器
```

## Components and Interfaces

### 1. Fake Blob Store

用于模拟流式大文件读取，避免真实 I/O 开销：

```python
class FakeBlobStore:
    """Fake blob store for performance testing."""

    async def head(self, key: str) -> dict:
        """Return file metadata including size."""

    async def get(self, key: str) -> bytes:
        """Return file content (for small files)."""

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content in chunks."""

    async def download_to_file(self, key: str, path: str) -> None:
        """Download file to local path."""
```

### 2. Memory Tracker

追踪测试期间的内存使用：

```python
class MemoryTracker:
    """Track memory usage during test execution."""

    def start(self) -> None:
        """Start memory tracking."""

    def stop(self) -> float:
        """Stop tracking and return peak memory (MB)."""

    def get_current(self) -> float:
        """Get current memory usage (MB)."""
```

### 3. Metrics Collector

收集性能指标：

```python
@dataclass
class PerformanceMetrics:
    """Performance test metrics."""
    qps: float
    p95_latency_ms: float
    peak_memory_mb: float
    duration_s: float
    cache_hit_rate: float | None = None
    throughput_mb_s: float | None = None
```

## Data Models

### 测试数据生成策略

```python
from hypothesis import strategies as st

# 文件大小生成器 (bytes)
file_size_small = st.integers(min_value=1024, max_value=10 * 1024 * 1024)  # 1KB-10MB
file_size_large = st.integers(min_value=100 * 1024 * 1024, max_value=500 * 1024 * 1024)  # 100MB-500MB

# 并发数生成器
concurrency_level = st.integers(min_value=1, max_value=20)

# 缓存命中率生成器
cache_hit_rate = st.floats(min_value=0.0, max_value=1.0)
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

### Property 1: 大文件 Ingest 内存限制

_For any_ file size between 100MB and 500MB, when ingested via streaming blob_store, the peak memory usage SHALL be at most 1.5x the file size.

**Validates: Requirements 1.1, 1.2**

### Property 2: 大文件 Ingest 耗时限制

_For any_ file size between 100MB and 500MB, when ingested via streaming blob_store, the processing time SHALL be at most (file_size_mb \* 0.6) seconds.

**Validates: Requirements 1.3, 1.4**

### Property 3: Semaphore 并发限制 - Retriever

_For any_ number of concurrent retrieval requests N > semaphore_limit, the system SHALL process at most semaphore_limit requests simultaneously.

**Validates: Requirements 2.1, 2.5**

### Property 4: Semaphore 并发限制 - Embedder

_For any_ number of concurrent embedding requests N > semaphore_limit, the system SHALL process at most semaphore_limit requests simultaneously.

**Validates: Requirements 2.2, 2.3**

### Property 5: Semaphore 队列行为

_For any_ number of concurrent requests exceeding semaphore limit, all requests SHALL eventually complete without rejection.

**Validates: Requirements 2.4**

### Property 6: Reranker 事件循环响应性

_For any_ reranking operation on N documents, concurrent async operations SHALL complete within their expected time (not blocked by reranking).

**Validates: Requirements 3.3, 3.4**

### Property 7: 语义缓存 QPS 提升

_For any_ cache hit rate >= 80%, the system QPS with semantic cache enabled SHALL be at least 3x the QPS with cache disabled.

**Validates: Requirements 4.1**

### Property 8: 语义缓存命中延迟

_For any_ semantic cache hit, the P95 latency SHALL be below 50ms.

**Validates: Requirements 4.2**

### Property 9: 语义缓存退化性能

_For any_ cache hit rate >= 20%, the system QPS with semantic cache enabled SHALL be at least 1.2x the QPS with cache disabled.

**Validates: Requirements 4.4**

### Property 10: 多模态缓存吞吐提升

_For any_ cache hit rate >= 80%, the multimodal embedding throughput with cache enabled SHALL be at least 5x the throughput with cache disabled.

**Validates: Requirements 5.1**

### Property 11: 缓存 LRU 淘汰

_For any_ cache at maxsize capacity, adding a new entry SHALL evict the least recently used entry without errors.

**Validates: Requirements 5.4**

### Property 12: Embedding 缓存吞吐提升

_For any_ cache hit rate >= 80%, the BatchEmbedder throughput with cache enabled SHALL be at least 4x the throughput with cache disabled.

**Validates: Requirements 6.1**

### Property 13: Embedding 缓存大小限制

_For any_ number of cached embeddings, the cache size SHALL never exceed the configured maxsize.

**Validates: Requirements 6.2**

## Error Handling

### 性能测试错误

| 错误场景       | 预期行为               | 错误类型       |
| :------------- | :--------------------- | :------------- |
| 内存超限       | 测试失败，报告实际内存 | AssertionError |
| 耗时超限       | 测试失败，报告实际耗时 | AssertionError |
| Semaphore 泄漏 | 测试失败，报告未释放数 | AssertionError |
| 缓存性能不达标 | 测试失败，报告实际指标 | AssertionError |

## Testing Strategy

### 属性测试 (Property-Based Testing)

使用 **hypothesis** 库进行属性测试：

```python
# requirements-dev.txt
hypothesis>=6.0.0
pytest-benchmark>=4.0.0
psutil>=5.9.0  # 内存追踪
```

每个属性测试配置运行至少 100 次迭代：

```python
from hypothesis import settings

@settings(max_examples=100)
@given(...)
def test_property_xxx(...):
    ...
```

### 基准测试

使用 pytest-benchmark 进行基准测试：

```python
def test_cache_performance(benchmark):
    result = benchmark(cache_operation)
    assert result.stats.mean < threshold
```

### 测试标注格式

每个属性测试必须包含注释：

```python
# **Feature: performance-tests, Property 1: 大文件 Ingest 内存限制**
# **Validates: Requirements 1.1, 1.2**
```

## 测试用例清单

### 大文件 Ingest 性能

| 用例 ID   | 描述               | 输入                | 预期输出            |
| :-------- | :----------------- | :------------------ | :------------------ |
| TC-LF-001 | 100MB 文件内存限制 | 100MB fake file     | peak_memory ≤ 150MB |
| TC-LF-002 | 500MB 文件内存限制 | 500MB fake file     | peak_memory ≤ 750MB |
| TC-LF-003 | 100MB 文件耗时限制 | 100MB fake file     | duration ≤ 60s      |
| TC-LF-004 | 500MB 文件耗时限制 | 500MB fake file     | duration ≤ 300s     |
| TC-LF-005 | 无流式支持拒绝     | 200MB, no streaming | RuntimeError        |

### 并发控制测试

| 用例 ID   | 描述                   | 输入                   | 预期输出                   |
| :-------- | :--------------------- | :--------------------- | :------------------------- |
| TC-CC-001 | Retriever semaphore=3  | 10 concurrent requests | max_concurrent ≤ 3         |
| TC-CC-002 | Embedder semaphore=4   | 10 concurrent requests | max_concurrent ≤ 4         |
| TC-CC-003 | BatchEmbedder 动态配置 | concurrency=5          | max_concurrent ≤ 5         |
| TC-CC-004 | 队列不拒绝             | 20 requests, sem=3     | all complete               |
| TC-CC-005 | Semaphore 释放         | 10 requests            | semaphore.\_value restored |

### Reranker 非阻塞测试

| 用例 ID   | 描述                   | 输入                      | 预期输出                |
| :-------- | :--------------------- | :------------------------ | :---------------------- |
| TC-RR-001 | 同步 reranker 包装     | sync reranker             | to_thread called        |
| TC-RR-002 | 异步 reranker 直接调用 | async reranker            | direct call             |
| TC-RR-003 | 事件循环响应           | 100 docs + concurrent ops | concurrent ops complete |
| TC-RR-004 | 非阻塞验证             | rerank + timer            | timer fires on time     |

### 缓存性能对比

| 用例 ID   | 描述                   | 输入                     | 预期输出                 |
| :-------- | :--------------------- | :----------------------- | :----------------------- |
| TC-SC-001 | 语义缓存 80% hit QPS   | 1000 queries, 80% hit    | QPS ≥ 3x baseline        |
| TC-SC-002 | 语义缓存命中延迟       | cache hit                | P95 ≤ 50ms               |
| TC-SC-003 | 语义缓存 20% hit QPS   | 1000 queries, 20% hit    | QPS ≥ 1.2x baseline      |
| TC-MC-001 | 多模态缓存 80% hit     | 1000 embeds, 80% hit     | throughput ≥ 5x baseline |
| TC-MC-002 | 多模态缓存 TTL 过期    | expired entry            | re-embed                 |
| TC-MC-003 | 多模态缓存 LRU 淘汰    | full cache + new entry   | LRU evicted              |
| TC-EC-001 | Embedding 缓存 80% hit | 1000 texts, 80% hit      | throughput ≥ 4x baseline |
| TC-EC-002 | Embedding 缓存大小限制 | 15000 entries, max=10000 | size ≤ 10000             |

## 性能报告格式

```json
{
  "test_suite": "performance-tests",
  "timestamp": "2025-12-12T10:00:00Z",
  "results": {
    "large_file_ingest": {
      "100mb": {
        "peak_memory_mb": 142.5,
        "duration_s": 45.2,
        "throughput_mb_s": 2.21,
        "status": "PASS"
      },
      "500mb": {
        "peak_memory_mb": 680.3,
        "duration_s": 210.5,
        "throughput_mb_s": 2.37,
        "status": "PASS"
      }
    },
    "concurrency_control": {
      "retriever_semaphore": {
        "configured_limit": 3,
        "max_observed_concurrent": 3,
        "all_completed": true,
        "status": "PASS"
      }
    },
    "cache_comparison": {
      "semantic_cache": {
        "baseline_qps": 50.2,
        "cached_qps_80_hit": 165.8,
        "improvement_factor": 3.3,
        "p95_latency_ms": 42.1,
        "status": "PASS"
      }
    }
  }
}
```
