# Requirements Document

## Introduction

本需求文档定义了 OmniRAG 系统的性能测试需求，覆盖三个核心场景：

1. 大文件 ingest 内存与耗时（使用 fake blob_store 流式处理）
2. 并发检索/嵌入的 semaphore 控制与 reranker async 非阻塞验证
3. 缓存命中率与退化性能对比（语义缓存、多模态缓存、embedding 缓存）

## Glossary

- **blob_store**: 对象存储抽象层，支持流式读写大文件
- **Semaphore**: 异步信号量，用于控制并发数量
- **Reranker**: 重排序器，对检索结果进行二次排序
- **Semantic Cache**: 语义缓存，基于查询相似度缓存检索结果
- **Multimodal Cache**: 多模态缓存，缓存图像/文本嵌入向量
- **Embedding Cache**: 嵌入缓存，LRU+TTL 策略缓存向量
- **QPS**: Queries Per Second，每秒查询数
- **P95 Latency**: 95th 百分位延迟
- **Peak Memory**: 峰值内存使用量

## Requirements

### Requirement 1: 大文件 Ingest 性能

**User Story:** As a system operator, I want to ingest large files (100MB-500MB) with controlled memory usage, so that the system remains stable under heavy document loads.

#### Acceptance Criteria

1. WHEN ingesting a 100MB file via streaming blob_store THEN the system SHALL maintain peak memory below 150MB (1.5x file size)
2. WHEN ingesting a 500MB file via streaming blob_store THEN the system SHALL maintain peak memory below 750MB (1.5x file size)
3. WHEN ingesting a 100MB file THEN the system SHALL complete within 60 seconds (excluding network I/O)
4. WHEN ingesting a 500MB file THEN the system SHALL complete within 300 seconds (excluding network I/O)
5. WHEN blob_store streaming is unavailable for files >100MB THEN the system SHALL reject the request with RuntimeError

### Requirement 2: 并发检索/嵌入 Semaphore 控制

**User Story:** As a developer, I want concurrent retrieval and embedding operations to be rate-limited by semaphores, so that system resources are protected from overload.

#### Acceptance Criteria

1. WHEN MultimodalRetriever processes concurrent requests THEN the semaphore SHALL limit concurrent operations to configured value (default: 3)
2. WHEN MultimodalEmbedder processes concurrent requests THEN the semaphore SHALL limit concurrent operations to configured value (default: 4)
3. WHEN BatchEmbedder processes concurrent requests THEN the semaphore SHALL limit concurrent operations to strategy_config.embedding_concurrency
4. WHEN semaphore limit is reached THEN additional requests SHALL queue without rejection
5. WHEN 10 concurrent retrieval requests are submitted with semaphore=3 THEN the system SHALL process at most 3 simultaneously

### Requirement 3: Reranker Async 非阻塞验证

**User Story:** As a developer, I want the reranker to not block the event loop, so that other async operations can proceed during reranking.

#### Acceptance Criteria

1. WHEN CrossEncoderReranker calls a sync reranker.score() THEN the system SHALL wrap it in asyncio.to_thread()
2. WHEN CrossEncoderReranker calls an async reranker.score() THEN the system SHALL call it directly without thread wrapping
3. WHEN reranking 100 documents THEN the event loop SHALL remain responsive (other coroutines can execute)
4. WHEN reranking is in progress THEN concurrent async operations SHALL complete within expected time (not blocked)

### Requirement 4: 语义缓存性能对比

**User Story:** As a system operator, I want to measure semantic cache performance impact, so that I can make informed decisions about cache configuration.

#### Acceptance Criteria

1. WHEN semantic cache is enabled with 80% hit rate THEN the system SHALL achieve at least 3x QPS improvement over disabled cache
2. WHEN semantic cache is enabled THEN the P95 latency for cache hits SHALL be below 50ms
3. WHEN semantic cache is disabled THEN the system SHALL still function with baseline performance
4. WHEN cache hit rate drops to 20% THEN the system SHALL maintain at least 1.2x QPS improvement over disabled cache
5. WHEN measuring cache performance THEN the test SHALL report hit rate, QPS, and P95 latency metrics

### Requirement 5: 多模态缓存性能对比

**User Story:** As a system operator, I want to measure multimodal embedding cache performance, so that I can optimize image/text embedding operations.

#### Acceptance Criteria

1. WHEN multimodal cache is enabled with 80% hit rate THEN the embedding throughput SHALL improve by at least 5x
2. WHEN multimodal cache TTL expires THEN the system SHALL re-embed and update cache
3. WHEN multimodal cache is disabled THEN the system SHALL embed every request without caching
4. WHEN cache is full (maxsize reached) THEN the system SHALL evict LRU entries without errors
5. WHEN measuring cache performance THEN the test SHALL report hit rate, throughput, and memory usage

### Requirement 6: Embedding 缓存性能对比

**User Story:** As a system operator, I want to measure BatchEmbedder LRU cache performance, so that I can tune cache size for optimal performance.

#### Acceptance Criteria

1. WHEN embedding cache is enabled with 80% hit rate THEN the embedding throughput SHALL improve by at least 4x
2. WHEN embedding cache maxsize is 10000 THEN the system SHALL maintain cache size at or below limit
3. WHEN embedding cache is disabled THEN the system SHALL embed every text without caching
4. WHEN cache key collision occurs THEN the system SHALL handle it gracefully (overwrite or skip)
5. WHEN measuring cache performance THEN the test SHALL report hit rate, throughput, and cache size metrics

### Requirement 7: 综合性能验收标准

**User Story:** As a QA engineer, I want clear performance acceptance criteria, so that I can validate system performance objectively.

#### Acceptance Criteria

1. WHEN running large file ingest benchmark THEN the report SHALL include peak memory (MB), duration (s), and throughput (MB/s)
2. WHEN running concurrent retrieval benchmark THEN the report SHALL include QPS, P95 latency (ms), and semaphore utilization (%)
3. WHEN running cache comparison benchmark THEN the report SHALL include hit rate (%), QPS delta (%), and memory overhead (MB)
4. WHEN any performance metric exceeds threshold THEN the test SHALL fail with clear error message
5. WHEN performance tests complete THEN the system SHALL generate a summary report with all metrics

## Performance Acceptance Thresholds

| 场景                     | 指标         | 阈值    |
| :----------------------- | :----------- | :------ |
| 100MB 文件 Ingest        | 峰值内存     | ≤ 150MB |
| 100MB 文件 Ingest        | 耗时         | ≤ 60s   |
| 500MB 文件 Ingest        | 峰值内存     | ≤ 750MB |
| 500MB 文件 Ingest        | 耗时         | ≤ 300s  |
| 并发检索 (10 req, sem=3) | 同时执行数   | ≤ 3     |
| 并发检索                 | P95 延迟     | ≤ 500ms |
| Reranker 非阻塞          | 事件循环响应 | ≤ 10ms  |
| 语义缓存 (80% hit)       | QPS 提升     | ≥ 3x    |
| 语义缓存命中             | P95 延迟     | ≤ 50ms  |
| 多模态缓存 (80% hit)     | 吞吐提升     | ≥ 5x    |
| Embedding 缓存 (80% hit) | 吞吐提升     | ≥ 4x    |
