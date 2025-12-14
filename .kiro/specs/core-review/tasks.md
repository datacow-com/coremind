# Core 审查问题修复任务清单

## 实现计划

- [x] 1. P0 多租户隔离修复 (立即)

  - [x] 1.1 GraphRAG Light 添加 channel_id 字段
    - 修改 `core/algorithms/graphrag_light.py` 中的 `GraphLightState` TypedDict
    - 添加 `channel_id: str` 字段
    - 更新 `light_collect` 函数确保 channel_id 传递
    - _Requirements: P0-1_
  - [x] 1.2 RAPTOR Light 添加 channel_id 字段
    - 修改 `core/algorithms/raptor_light.py` 中的 `RaptorLightState` TypedDict
    - 添加 `channel_id: str` 字段
    - 更新 `light_collect` 函数确保 channel_id 传递
    - _Requirements: P0-2_
  - [x] 1.3 MultimodalRetriever.search() 添加 channel_id 参数
    - 修改 `core/retrieval/multimodal/retriever.py` 中的 `search()` 方法签名
    - 添加 `channel_id: str` 必需参数
    - 更新 `_search_kb()` 调用传递 channel_id
    - _Requirements: P0-3_

- [-] 2. P1 Ingestion Graph 修复

  - [ ] 2.1 添加 error_handler 条件边
    - 修改 `core/ingestion/graph.py`
    - 添加 `_check_indexer_error()` 路由函数
    - 将 `indexer -> finalizer` 边改为条件边
    - 添加 `indexer -> error_handler` 路径
    - _Requirements: P1-1_

- [ ] 3. P1 检索链路修复

  - [ ] 3.1 RRF 融合应用 metadata 权重
    - 修改 `core/retrieval/nodes/retriever.py` 中的 `_rrf_fusion()` 方法
    - 读取 chunk metadata 中的 type_weight, heading_weight, position_weight
    - 计算加权分数并应用
    - _Requirements: P1-4_
  - [ ] 3.2 SemanticCache 节点接入修复
    - 修改 `core/graph.py`
    - 创建 `_semantic_cache_check()` 和 `_semantic_cache_store()` 包装函数
    - 替换直接方法引用为包装函数
    - _Requirements: P1-5_

- [ ] 4. P1 LLM 和 Embedding 修复

  - [ ] 4.1 LLMGateway 熔断状态共享
    - 修改 `core/llm/gateway.py`
    - 将 `_cb_state` 和 `_cb_cooldown` 改为类变量
    - 添加 `threading.Lock` 保护并发访问
    - 更新 `_cb_allowed()`, `_cb_on_fail()`, `_cb_on_success()` 方法
    - _Requirements: P1-6_
  - [ ] 4.2 BatchEmbedder 添加 LRU 缓存
    - 修改 `core/ingestion/nodes/embedder.py`
    - 添加类级别 `LRUCache` (maxsize=10000)
    - 实现 `_cache_key()` 方法
    - 在 `__call__()` 中先检查缓存再调用 embedder
    - 更新 `requirements.txt` 添加 `cachetools>=5.0.0`
    - _Requirements: P1-7_

- [ ] 5. P1 索引修复

  - [ ] 5.1 DualIndexer 图像集合检查
    - 修改 `core/ingestion/nodes/indexer.py` 中的 `_index_images()` 方法
    - 在 upsert 前添加 `await vector_client.ensure_collection()` 调用
    - _Requirements: P1-8_

- [ ] 6. 单元测试

  - [ ] 6.1 P0 多租户隔离测试
    - 创建 `tests/core/test_algorithm_channel.py`
    - 测试 GraphRAG Light channel_id 必需性
    - 测试 RAPTOR Light channel_id 必需性
    - 测试 MultimodalRetriever.search() channel_id 必需性
    - _Requirements: P0-1, P0-2, P0-3_
  - [ ] 6.2 P1 功能测试
    - 创建 `tests/core/test_ingestion_error_handler.py`
    - 创建 `tests/core/test_retriever_weights.py`
    - 创建 `tests/core/test_embedder_cache.py`
    - _Requirements: P1-1, P1-4, P1-7_

- [ ] 7. 集成测试和文档
  - [ ] 7.1 更新 API 文档
    - 更新 `docs/api-spec.md` 中 search() 签名变更说明
    - 添加 channel_id 参数说明
    - _Requirements: P0-3_
  - [ ] 7.2 运行集成测试验证
    - 运行 `pytest tests/core/ -v`
    - 验证所有修复生效
    - _Requirements: All_
