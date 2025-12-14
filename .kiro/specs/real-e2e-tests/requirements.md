# Requirements Document

## Introduction

本规格定义了 OmniRAG 核心模块的真实环境端到端（E2E）与集成测试需求。测试将使用 `tests/core/docs` 目录下的真实文档（PDF、Word、PPTX、图片等），连接 docker-compose 启动的真实依赖服务（Qdrant、Elasticsearch、MinIO、Redis 等），禁止使用 mock。

测试目标是验证 `core/` 模块在真实数据和真实依赖下的正确性、多租户隔离、错误处理和性能表现。

## Glossary

- **OmniRAG**: 本项目的 RAG（Retrieval-Augmented Generation）系统
- **Channel**: 多租户隔离单元，每个 channel 拥有独立的向量集合和关键词索引
- **Ingestion Pipeline**: 文档摄取管道，包括加载、解析、分块、嵌入、索引等阶段
- **Retrieval Pipeline**: 检索管道，包括预处理、向量检索、关键词检索、重排序、生成等阶段
- **Qdrant**: 向量数据库，用于存储和检索文档向量
- **Elasticsearch**: 关键词搜索引擎，用于 BM25 检索
- **MinIO**: 对象存储服务，用于存储原始文档
- **Redis**: 缓存服务，用于语义缓存
- **Semantic Cache**: 语义缓存，基于查询相似度缓存检索结果
- **RRF (Reciprocal Rank Fusion)**: 混合检索结果融合算法
- **CrossEncoder Reranker**: 基于交叉编码器的重排序模型
- **ZIP Bomb**: 恶意压缩文件，解压后体积远超压缩包大小
- **Chunking Strategy**: 分块策略，包括 fixed、semantic、layout_aware、table_first
- **StrategyConfig**: 策略配置对象，支持平铺和嵌套两种访问模式

## Requirements

### Requirement 1: Ingestion Pipeline Real Document Testing

**User Story:** As a QA engineer, I want to test the ingestion pipeline with real documents from `tests/core/docs`, so that I can verify the system correctly processes various document formats under real conditions.

#### Acceptance Criteria

1.1. WHEN the ingestion pipeline processes a large PDF file (>5MB) THEN the OmniRAG System SHALL use lazy loading to avoid memory exhaustion and complete processing within 120 seconds

1.2. WHEN the ingestion pipeline encounters a document on a system without GPU THEN the OmniRAG System SHALL route to CPU parser and skip GPU-specific tests with appropriate skip reason

1.3. WHEN the ingestion pipeline receives a ZIP file containing more than 100 files or exceeding 500MB uncompressed THEN the OmniRAG System SHALL reject the file and record an error in error_log with reason "zip_bomb_protection"

1.4. WHEN the ingestion pipeline processes a PDF containing mixed tables and images THEN the OmniRAG System SHALL extract both table structures and image content with appropriate block_type metadata

1.5. WHEN the ingestion pipeline uses different chunking strategies (fixed, semantic, layout_aware, table_first) THEN the OmniRAG System SHALL produce different chunk counts and preserve table integrity when preserve_tables is enabled

1.6. WHEN the ingestion pipeline completes embedding THEN the OmniRAG System SHALL write vectors to Qdrant and keywords to Elasticsearch with matching document counts

1.7. WHEN the ingestion pipeline completes THEN the OmniRAG System SHALL clean up all temporary files in the processing directory

1.8. WHEN the ingestion pipeline indexes documents for channel_A THEN the OmniRAG System SHALL store chunks in channel_A-prefixed collections and indexes only

### Requirement 2: Retrieval Pipeline Real Document Testing

**User Story:** As a QA engineer, I want to test the retrieval pipeline against pre-indexed real documents, so that I can verify semantic cache, hybrid retrieval, reranking, and multi-tenant isolation work correctly.

#### Acceptance Criteria

2.1. WHEN a query is executed for the first time THEN the OmniRAG System SHALL miss the semantic cache and execute the full retrieval pipeline (retriever → reranker → generator)

2.2. WHEN the same query is executed again within cache TTL THEN the OmniRAG System SHALL hit the semantic cache and skip retriever and reranker nodes

2.3. WHEN hybrid retrieval is enabled THEN the OmniRAG System SHALL combine vector results from Qdrant and keyword results from Elasticsearch using RRF fusion

2.4. WHEN CrossEncoder reranker is enabled THEN the OmniRAG System SHALL reorder fused results by rerank_score and return top_k results

2.5. WHEN web_search intent is detected but external network is unavailable THEN the OmniRAG System SHALL skip web search gracefully and fall back to local retrieval

2.6. WHEN hallucination_check is enabled and hallucination_score exceeds threshold THEN the OmniRAG System SHALL reduce confidence score and add warning prefix to final_answer

2.7. WHEN a query is executed against channel_A THEN the OmniRAG System SHALL return only chunks from channel_A and zero results from channel_B

2.8. WHEN retrieval completes successfully THEN the OmniRAG System SHALL return citations with doc_id, page_num, and content fields

### Requirement 3: Storage Layer Real Integration Testing

**User Story:** As a QA engineer, I want to test the storage layer with real Qdrant and Elasticsearch instances, so that I can verify channel isolation, dual-write consistency, and error handling.

#### Acceptance Criteria

3.1. WHEN channel*utils generates collection names THEN the OmniRAG System SHALL prefix collection names with channel_id following the pattern "{channel_id}*{base_name}"

3.2. WHEN index_router queries with pagination THEN the OmniRAG System SHALL return stable results across multiple scroll requests

3.3. WHEN vectors are written to Qdrant and keywords to Elasticsearch THEN the OmniRAG System SHALL maintain equal document counts in both stores

3.4. WHEN vectors with incorrect dimensions are written to Qdrant THEN the OmniRAG System SHALL raise an error and record it in error_log

3.5. WHEN batch write fails due to transient error THEN the OmniRAG System SHALL retry up to 3 times and succeed on recovery

3.6. WHEN querying channel_A's collection THEN the OmniRAG System SHALL return zero results for documents indexed under channel_B

### Requirement 4: State and Configuration Testing

**User Story:** As a QA engineer, I want to test StrategyConfig with real ingestion and retrieval flows, so that I can verify flat/nested compatibility and effective property handling.

#### Acceptance Criteria

4.1. WHEN StrategyConfig receives flat fields (chunking_mode, chunk_size) THEN the OmniRAG System SHALL use flat values over nested chunking object values

4.2. WHEN StrategyConfig effective properties receive falsy values (0, False) THEN the OmniRAG System SHALL treat them as valid values and not fall back to defaults

4.3. WHEN IngestState or RetrievalState is created without channel_id THEN the OmniRAG System SHALL raise a validation error

4.4. WHEN StrategyConfig is serialized to JSON and deserialized THEN the OmniRAG System SHALL produce an equivalent configuration object

4.5. WHEN a minimal StrategyConfig drives the ingestion pipeline THEN the OmniRAG System SHALL complete successfully with default values applied

### Requirement 5: Algorithm Module Real Integration Testing

**User Story:** As a QA engineer, I want to test RAPTOR, GraphRAG, and MindMap algorithms with real indexed documents, so that I can verify pagination, channel filtering, and graceful degradation.

#### Acceptance Criteria

5.1. WHEN raptor_light or raptor_deep is executed on indexed documents THEN the OmniRAG System SHALL return clustered summaries with pagination support

5.2. WHEN graphrag_light or graphrag_deep is executed THEN the OmniRAG System SHALL build entity-relation graphs filtered by channel_id

5.3. WHEN mindmap_light is executed THEN the OmniRAG System SHALL generate hierarchical topic structures from indexed chunks

5.4. WHEN required models or dependencies are missing THEN the OmniRAG System SHALL skip the test with importorskip and provide reason

5.5. WHEN algorithm results are paginated THEN the OmniRAG System SHALL return consistent results across page boundaries

5.6. WHEN algorithm queries specify channel_A THEN the OmniRAG System SHALL exclude documents from channel_B in all results
