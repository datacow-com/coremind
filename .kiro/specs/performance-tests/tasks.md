# Implementation Plan

- [x] 1. 设置性能测试基础设施

  - [x] 1.1 创建测试目录和工具模块
    - 创建 `tests/core/performance/` 目录
    - 创建 `tests/core/performance/__init__.py`
    - 创建 `tests/core/performance/utils/` 目录
    - _Requirements: 7.1_
  - [x] 1.2 实现 FakeBlobStore
    - 创建 `tests/core/performance/utils/fake_blob_store.py`
    - 实现 `head()`, `get()`, `stream()`, `download_to_file()` 方法
    - 支持配置文件大小和流式块大小
    - _Requirements: 1.1, 1.2_
  - [x] 1.3 实现 MemoryTracker
    - 创建 `tests/core/performance/utils/memory_tracker.py`
    - 使用 psutil 追踪进程内存
    - 实现 `start()`, `stop()`, `get_current()`, `get_peak()` 方法
    - _Requirements: 1.1, 1.2, 7.1_
  - [x] 1.4 实现 MetricsCollector
    - 创建 `tests/core/performance/utils/metrics_collector.py`
    - 定义 `PerformanceMetrics` dataclass
    - 实现 QPS、P95 延迟、吞吐量计算
    - _Requirements: 7.1, 7.2, 7.3_
  - [x] 1.5 创建 conftest.py
    - 创建 `tests/core/performance/conftest.py`
    - 定义共享 fixtures: fake_blob_store, memory_tracker, metrics_collector
    - 定义 hypothesis strategies
    - _Requirements: 7.1_

- [x] 2. 大文件 Ingest 性能测试

  - [x] 2.1 创建大文件测试文件
    - 创建 `tests/core/performance/test_large_file_ingest.py`
    - _Requirements: 1.1-1.5_
  - [x] 2.2 实现 Property 1: 大文件内存限制
    - 测试 100MB-500MB 文件 ingest 内存 ≤ 1.5x 文件大小
    - **Property 1: 大文件 Ingest 内存限制**
    - **Validates: Requirements 1.1, 1.2**
    - _Requirements: 1.1, 1.2_
  - [ ]\* 2.3 实现 Property 2: 大文件耗时限制
    - 测试 100MB-500MB 文件 ingest 耗时 ≤ file_size_mb \* 0.6s
    - **Property 2: 大文件 Ingest 耗时限制**
    - **Validates: Requirements 1.3, 1.4**
    - _Requirements: 1.3, 1.4_
  - [x] 2.4 实现无流式支持拒绝测试 (TC-LF-005)
    - 测试 blob_store 无 streaming 时拒绝 >100MB 文件
    - _Requirements: 1.5_

- [x] 3. Checkpoint - 确保大文件测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [-] 4. 并发控制测试

  - [x] 4.1 创建并发控制测试文件
    - 创建 `tests/core/performance/test_concurrency_control.py`
    - _Requirements: 2.1-2.5_
  - [x] 4.2 实现 Property 3: Retriever Semaphore 限制
    - 测试 N > semaphore_limit 时最多同时处理 semaphore_limit 个请求
    - **Property 3: Semaphore 并发限制 - Retriever**
    - **Validates: Requirements 2.1, 2.5**
    - _Requirements: 2.1, 2.5_
  - [x] 4.3 实现 Property 4: Embedder Semaphore 限制
    - 测试 MultimodalEmbedder 和 BatchEmbedder semaphore 限制
    - **Property 4: Semaphore 并发限制 - Embedder**
    - **Validates: Requirements 2.2, 2.3**
    - _Requirements: 2.2, 2.3_
  - [x] 4.4 实现 Property 5: Semaphore 队列行为
    - 测试超过 semaphore 限制的请求排队而非拒绝
    - **Property 5: Semaphore 队列行为**
    - **Validates: Requirements 2.4**
    - _Requirements: 2.4_

- [-] 5. Reranker 非阻塞测试

  - [x] 5.1 创建 Reranker 测试文件
    - 创建 `tests/core/performance/test_reranker_nonblocking.py`
    - _Requirements: 3.1-3.4_
  - [x] 5.2 实现同步 Reranker 包装测试 (TC-RR-001)
    - 验证 sync reranker.score() 被 asyncio.to_thread() 包装
    - _Requirements: 3.1_
  - [x] 5.3 实现异步 Reranker 直接调用测试 (TC-RR-002)
    - 验证 async reranker.score() 直接调用
    - _Requirements: 3.2_
  - [ ]\* 5.4 实现 Property 6: 事件循环响应性
    - 测试 reranking 期间其他 async 操作不被阻塞
    - **Property 6: Reranker 事件循环响应性**
    - **Validates: Requirements 3.3, 3.4**
    - _Requirements: 3.3, 3.4_

- [x] 6. Checkpoint - 确保并发和 Reranker 测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [-] 7. 缓存性能对比测试

  - [x] 7.1 创建缓存测试文件
    - 创建 `tests/core/performance/test_cache_comparison.py`
    - _Requirements: 4.1-4.5, 5.1-5.5, 6.1-6.5_
  - [ ]\* 7.2 实现 Property 7: 语义缓存 QPS 提升
    - 测试 80% hit rate 时 QPS ≥ 3x baseline
    - **Property 7: 语义缓存 QPS 提升**
    - **Validates: Requirements 4.1**
    - _Requirements: 4.1_
  - [ ]\* 7.3 实现 Property 8: 语义缓存命中延迟
    - 测试 cache hit P95 延迟 ≤ 50ms
    - **Property 8: 语义缓存命中延迟**
    - **Validates: Requirements 4.2**
    - _Requirements: 4.2_
  - [ ]\* 7.4 实现 Property 9: 语义缓存退化性能
    - 测试 20% hit rate 时 QPS ≥ 1.2x baseline
    - **Property 9: 语义缓存退化性能**
    - **Validates: Requirements 4.4**
    - _Requirements: 4.4_
  - [ ]\* 7.5 实现 Property 10: 多模态缓存吞吐提升
    - 测试 80% hit rate 时吞吐 ≥ 5x baseline
    - **Property 10: 多模态缓存吞吐提升**
    - **Validates: Requirements 5.1**
    - _Requirements: 5.1_
  - [ ]\* 7.6 实现 Property 11: 缓存 LRU 淘汰
    - 测试缓存满时 LRU 淘汰无错误
    - **Property 11: 缓存 LRU 淘汰**
    - **Validates: Requirements 5.4**
    - _Requirements: 5.4_
  - [ ]\* 7.7 实现 Property 12: Embedding 缓存吞吐提升
    - 测试 80% hit rate 时吞吐 ≥ 4x baseline
    - **Property 12: Embedding 缓存吞吐提升**
    - **Validates: Requirements 6.1**
    - _Requirements: 6.1_
  - [ ]\* 7.8 实现 Property 13: Embedding 缓存大小限制
    - 测试缓存大小不超过 maxsize
    - **Property 13: Embedding 缓存大小限制**
    - **Validates: Requirements 6.2**
    - _Requirements: 6.2_

- [ ] 8. 缓存基线测试

  - [ ] 8.1 实现语义缓存禁用基线 (TC-SC-003 baseline)
    - 测试 semantic cache 禁用时的基线性能
    - _Requirements: 4.3_
  - [ ] 8.2 实现多模态缓存 TTL 过期测试 (TC-MC-002)
    - 测试 TTL 过期后重新嵌入
    - _Requirements: 5.2_
  - [ ] 8.3 实现 Embedding 缓存禁用基线 (TC-EC baseline)
    - 测试 embedding cache 禁用时的基线性能
    - _Requirements: 6.3_

- [ ] 9. Final Checkpoint - 确保所有性能测试通过
  - Ensure all tests pass, ask the user if questions arise.
