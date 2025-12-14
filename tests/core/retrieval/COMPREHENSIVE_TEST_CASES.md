# 检索管道全模块测试用例规范

## 概述

本文档为 `core/graph.py` 和 `core/retrieval/nodes/**` 模块的全面测试用例规范，覆盖 LangGraph 条件路由、多租户隔离、缓存机制、错误注入等关键功能。

## 测试优先级定义

- **P0**: 崩溃/安全/越权问题，必须 100%通过
- **P1**: 核心功能/设计对齐，影响用户体验
- **P2**: 增强功能/性能优化，可接受部分失败

---

## 1. LangGraph 路由测试 (core/graph.py)

### 1.1 Intent 路由测试

#### TC-G001: 关键词快速路由 (P1)

**目的**: 验证关键词触发的快速路由决策
**步骤**:

1. 设置查询包含 WEB_TRIGGERS ("最新", "实时", "news")
2. 调用 IntentRouter
3. 验证路由到 web_search
   **期望**:

```python
assert state["intent"]["type"] == "web_search"
# 跳过LLM调用，直接路由
```

#### TC-G002: LLM 意图分类 (P1)

**目的**: 验证 LLM 驱动的意图分类
**步骤**:

1. 设置 use_llm_router=True
2. Mock LLM 返回 JSON 格式意图
3. 调用 IntentRouter
   **期望**:

```python
assert state["intent"]["type"] in ["qa", "web_search", "table_query", "image_query", "summary"]
assert "confidence" in state["intent"]
```

#### TC-G003: LLM 分类失败回退 (P1)

**目的**: 验证 LLM 调用失败时的默认行为
**步骤**:

1. Mock LLM 抛出异常
2. 调用 IntentRouter
   **期望**:

```python
assert state["intent"]["type"] == "qa"  # 默认回退
```

### 1.2 条件路由映射测试

#### TC-G004: Web Search 路由映射 (P0)

**目的**: 验证 web_search 意图正确映射到 WebSearchNode
**步骤**:

1. 设置 intent["type"] = "web_search"
2. 执行图路由
   **期望**: 路由到 "web_search" 节点

#### TC-G005: 语义缓存路由映射 (P0)

**目的**: 验证非 web_search 意图路由到语义缓存
**步骤**:

1. 设置 intent["type"] = "qa"
2. 执行图路由
   **期望**: 路由到 "semantic_cache" 节点

#### TC-G006: 缓存命中跳过检索 (P1)

**目的**: 验证缓存命中时跳过检索管道
**步骤**:

1. 设置 cache_hit=True
2. 执行缓存路由器
   **期望**: 直接路由到 "generate" 节点

### 1.3 幻觉检测和重试测试

#### TC-G007: 幻觉检测超阈值处理 (P1)

**目的**: 验证幻觉分数超阈值时的降权和警告
**步骤**:

1. Mock LLM 返回高幻觉分数 (>0.5)
2. 调用 HallucinationChecker
   **期望**:

```python
assert state["hallucination_detected"] is True
assert state["confidence"] < original_confidence
assert "⚠️ 警告" in state["final_answer"]
```

#### TC-G008: 幻觉重试机制 (P1)

**目的**: 验证高幻觉检测触发重试
**步骤**:

1. 设置幻觉分数超阈值
2. 验证重试计数和路由
   **期望**:

```python
assert state["hallucination_retry_count"] == 1
# 路由到 retry_web_search
```

### 1.4 相关性检查和回退测试

#### TC-G009: 不相关结果 Web 搜索回退 (P1)

**目的**: 验证检索结果不相关时触发 Web 搜索
**步骤**:

1. 设置 is_relevant=False
2. 设置 loop_count=0
3. 执行相关性路由器
   **期望**: 路由到 "web_search" 节点

#### TC-G010: 循环限制防止无限重试 (P0)

**目的**: 验证重试循环次数限制
**步骤**:

1. 设置 loop_count >= 1
2. 设置 is_relevant=False
   **期望**: 路由到 "generate" 而非 "web_search"

---

## 2. 查询预处理器测试 (preprocessor.py)

### 2.1 意图分类测试

#### TC-P001: 意图类型检测 (P1)

**目的**: 验证各种意图类型的正确检测
**步骤**:

1. 测试不同查询类型
2. 验证意图分类结果
   **期望**:

```python
# 表格查询
assert intent["type"] == "table_query"
assert intent["filters"]["block_type"] == "table"

# 图片查询
assert intent["type"] == "image_query"
```

#### TC-P002: 语言检测准确性 (P1)

**目的**: 验证中英文语言检测
**步骤**:

1. 提供中文和英文查询
2. 调用 QueryPreProcessor
   **期望**:

```python
assert state["intent"]["language"] in ["zh", "en"]
```

#### TC-P003: 查询重写功能 (P1)

**目的**: 验证查询重写去除礼貌用词和修正错误
**步骤**:

1. 提供包含"请问"、"谢谢"的查询
2. 验证重写结果
   **期望**:

```python
rewritten = state["preprocessed_queries"][0]
assert "请问" not in rewritten
assert len(rewritten) > 0
```

### 2.2 LLM 网关缓存测试

#### TC-P004: 网关实例缓存 (P1)

**目的**: 验证 LLMGateway 实例的缓存复用
**步骤**:

1. 多次调用相同配置的预处理器
2. 验证网关实例复用
   **期望**: 相同 provider:model 使用同一实例

#### TC-P005: 配置变化时缓存失效 (P1)

**目的**: 验证配置变化时创建新的网关实例
**步骤**:

1. 使用不同 provider/model 配置
2. 验证创建新实例
   **期望**: 不同配置使用不同实例

### 2.3 回退机制测试

#### TC-P006: LLM 调用失败回退 (P1)

**目的**: 验证 LLM 调用失败时的回退处理
**步骤**:

1. Mock LLM 调用抛出异常
2. 调用 QueryPreProcessor
   **期望**:

```python
assert state["intent"]["type"] == "factual"  # 默认回退
assert state["preprocessed_queries"] == [original_query]
```

#### TC-P007: JSON 解析失败处理 (P1)

**目的**: 验证 LLM 返回无效 JSON 时的处理
**步骤**:

1. Mock LLM 返回非 JSON 格式
2. 调用 QueryPreProcessor
   **期望**: 使用默认意图和原始查询

---

## 3. 混合检索器测试 (retriever.py)

### 3.1 多租户隔离测试

#### TC-R001: Channel ID 过滤验证 (P0)

**目的**: 验证 RRF 融合前的 channel_id 过滤
**步骤**:

1. 创建不同 channel_id 的检索结果
2. 调用 \_rrf_fusion 并传入 channel_id
   **期望**:

```python
# 只有匹配 channel_id 的结果被融合
fused_results = retriever._rrf_fusion(vec_res, kw_res, channel_id="tenant_a")
assert all(
    r.get("metadata", {}).get("channel_id") == "tenant_a"
    for r in fused_results
)
```

#### TC-R002: 跨租户数据泄露防护 (P0)

**目的**: 验证不同租户数据不会混合
**步骤**:

1. 并发执行两个不同 channel_id 的检索
2. 验证结果隔离
   **期望**: 结果中不包含其他租户数据

#### TC-R003: 遗留数据兼容性 (P1)

**目的**: 验证无 channel_id 的遗留数据处理
**步骤**:

1. 提供无 channel_id 的检索结果
2. 调用 \_rrf_fusion
   **期望**: 遗留数据被包含在结果中

### 3.2 知识库兼容性测试

#### TC-R004: kb_names 列表支持 (P1)

**目的**: 验证 kb_names 列表的多知识库检索
**步骤**:

1. 设置 kb_names = ["kb1", "kb2"]
2. 调用 HybridRetriever
   **期望**: 检索覆盖所有指定知识库

#### TC-R005: kb_name 单值兼容 (P1)

**目的**: 验证向后兼容的 kb_name 单值支持
**步骤**:

1. 设置 kb_name = "single_kb"
2. 不设置 kb_names
   **期望**:

```python
# 自动转换为列表
assert state.get("kb_names") == ["single_kb"]
```

### 3.3 意图过滤测试

#### TC-R006: 表格查询过滤 (P1)

**目的**: 验证 table_query 意图的块类型过滤
**步骤**:

1. 设置 intent["type"] = "table_query"
2. 调用 HybridRetriever
   **期望**:

```python
# Qdrant 和 ES 都应用表格过滤
assert qdrant_filter.must[0].key == "metadata.block_type"
assert es_filters["block_type"] == "table"
```

#### TC-R007: 图片查询过滤 (P1)

**目的**: 验证 image_query 意图的图片过滤
**步骤**:

1. 设置 intent["type"] = "image_query"
2. 验证过滤条件
   **期望**: 只检索 block_type="image" 的内容

### 3.4 存储降级测试

#### TC-R008: 向量存储不可用降级 (P1)

**目的**: 验证向量存储失败时的处理
**步骤**:

1. Mock vector_client.search 抛出异常
2. 调用 HybridRetriever
   **期望**: 只使用关键词检索结果

#### TC-R009: 关键词存储不可用降级 (P1)

**目的**: 验证关键词存储失败时的处理
**步骤**:

1. Mock keyword_client.search 抛出异常
2. 调用 HybridRetriever
   **期望**: 只使用向量检索结果

---

## 4. 重排序器测试 (reranker.py)

### 4.1 异步包装测试

#### TC-RR001: 同步重排序器异步包装 (P1)

**目的**: 验证同步 reranker.score() 的异步包装
**步骤**:

1. Mock 同步 reranker
2. 调用 CrossEncoderReranker
   **期望**: 使用 asyncio.to_thread 包装

#### TC-RR002: 异步重排序器直接调用 (P1)

**目的**: 验证异步 reranker 的直接调用
**步骤**:

1. Mock 异步 reranker
2. 调用 CrossEncoderReranker
   **期望**: 直接 await 调用

### 4.2 阈值过滤测试

#### TC-RR003: 重排序阈值过滤 (P1)

**目的**: 验证低分结果被阈值过滤
**步骤**:

1. 设置 rerank_threshold=0.5
2. Mock 返回不同分数的结果
   **期望**:

```python
reranked = state["reranked_results"]
assert all(doc["rerank_score"] >= 0.5 for doc in reranked)
```

#### TC-RR004: 空结果处理 (P1)

**目的**: 验证无结果通过阈值时的处理
**步骤**:

1. 设置高阈值
2. Mock 低分结果
   **期望**:

```python
assert state["reranked_results"] == []
assert state["is_relevant"] is False
```

### 4.3 缓存并发安全测试

#### TC-RR005: 重排序器实例缓存 (P1)

**目的**: 验证重排序器实例的 TTL 缓存
**步骤**:

1. 多次调用相同配置
2. 验证缓存命中
   **期望**: 5 分钟内复用同一实例

#### TC-RR006: 缓存 TTL 过期 (P1)

**目的**: 验证缓存过期后重新创建实例
**步骤**:

1. Mock 时间超过 TTL
2. 调用重排序器
   **期望**: 创建新实例

#### TC-RR007: 并发缓存安全 (P2)

**目的**: 验证并发访问缓存的线程安全
**步骤**:

1. 并发调用重排序器
2. 验证无竞态条件
   **期望**: 缓存操作线程安全

### 4.4 置信度计算测试

#### TC-RR008: 检索置信度计算 (P1)

**目的**: 验证基于重排序分数的置信度计算
**步骤**:

1. 提供不同分数的重排序结果
2. 验证置信度计算
   **期望**:

```python
# 基于前3个结果的平均分
assert 0.0 <= state["retrieval_confidence"] <= 1.0
```

---

## 5. 引用生成器测试 (generator.py)

### 5.1 引用解析测试

#### TC-G001: 引用标签解析 (P1)

**目的**: 验证 `<cite id="[索引]">内容</cite>` 的正确解析
**步骤**:

1. Mock LLM 返回包含引用标签的答案
2. 调用 CitationGenerator
   **期望**:

```python
citations = state["citations"]
assert len(citations) > 0
assert citations[0]["doc_id"] is not None
assert citations[0]["content"] is not None
```

#### TC-G002: 无效引用索引处理 (P1)

**目的**: 验证超出范围的引用索引处理
**步骤**:

1. Mock 答案包含 `<cite id="[99]">内容</cite>`
2. 只提供 3 个文档
   **期望**: 无效引用被忽略

#### TC-G003: 引用元数据提取 (P1)

**目的**: 验证引用的完整元数据提取
**步骤**:

1. 提供包含 bbox、page_num 的文档
2. 验证引用元数据
   **期望**:

```python
citation = citations[0]
assert "doc_id" in citation
assert "page" in citation
assert "bbox" in citation
assert "chunk_id" in citation
```

### 5.2 置信度计算测试

#### TC-G004: 多因素置信度计算 (P1)

**目的**: 验证基于检索置信度和引用覆盖率的综合置信度
**步骤**:

1. 设置不同的检索置信度
2. 提供不同引用覆盖率的答案
   **期望**:

```python
# 有引用: retrieval_confidence * 0.6 + citation_coverage * 0.4
# 无引用但诚实: 0.3
# 无引用有答案: retrieval_confidence * 0.5
```

#### TC-G005: 诚实"不知道"答案处理 (P1)

**目的**: 验证"无法回答"类答案的置信度
**步骤**:

1. Mock LLM 返回"根据提供的资料无法回答"
2. 验证置信度设置
   **期望**:

```python
assert "无法回答" in state["final_answer"]
assert state["confidence"] == 0.3
```

### 5.3 LLM 配置缓存测试

#### TC-G006: 网关缓存复用 (P1)

**目的**: 验证相同配置的 LLM 网关缓存
**步骤**:

1. 多次调用相同 provider:model
2. 验证网关实例复用
   **期望**: 使用缓存的网关实例

#### TC-G007: 配置变化缓存失效 (P1)

**目的**: 验证 LLM 配置变化时缓存失效
**步骤**:

1. 更改 llm_provider 或 llm_model
2. 调用生成器
   **期望**: 创建新的网关实例

### 5.4 可配置提示词测试

#### TC-G008: 自定义系统提示词 (P2)

**目的**: 验证自定义系统提示词的使用
**步骤**:

1. 设置 generation_system_prompt
2. 调用 CitationGenerator
   **期望**: 使用自定义提示词而非默认

#### TC-G009: 自定义用户提示词模板 (P2)

**目的**: 验证自定义用户提示词模板
**步骤**:

1. 设置 generation_user_prompt 模板
2. 验证模板变量替换
   **期望**: 正确替换 {context} 和 {query}

---

## 6. 语义缓存测试 (semantic_cache.py)

### 6.1 缓存命中/未命中测试

#### TC-SC001: 语义相似查询缓存命中 (P1)

**目的**: 验证语义相似查询的缓存命中
**步骤**:

1. 缓存查询"什么是 AI"的答案
2. 查询"AI 是什么"
3. 验证缓存命中
   **期望**:

```python
assert state["cache_hit"] is True
assert state["final_answer"] == cached_answer
assert state["skip_retrieval"] is True
```

#### TC-SC002: 语义不相似查询缓存未命中 (P1)

**目的**: 验证不相似查询的缓存未命中
**步骤**:

1. 缓存"AI"相关答案
2. 查询完全不同主题
   **期望**:

```python
assert state["cache_hit"] is False
assert "_query_embedding" in state
```

#### TC-SC003: 相似度阈值控制 (P1)

**目的**: 验证相似度阈值对缓存命中的影响
**步骤**:

1. 设置不同 similarity_threshold
2. 测试边界相似度查询
   **期望**: 阈值控制缓存命中行为

### 6.2 TTL 和过期测试

#### TC-SC004: 缓存 TTL 过期 (P1)

**目的**: 验证缓存条目的 TTL 过期
**步骤**:

1. 缓存答案并 Mock 时间推进
2. 超过 ttl_seconds 后查询
   **期望**: 过期条目被清理，缓存未命中

#### TC-SC005: 缓存大小限制 (P1)

**目的**: 验证缓存大小超限时的 LRU 清理
**步骤**:

1. 设置小的 max_cache_size
2. 添加超过限制的缓存条目
   **期望**: 最老的条目被清理

### 6.3 嵌入哈希冲突测试

#### TC-SC006: 嵌入哈希冲突风险 (P2)

**目的**: 验证 \_embedding_hash 的冲突处理
**步骤**:

1. 创建相似但不同的嵌入向量
2. 验证哈希值处理
   **期望**: 不同嵌入产生不同哈希

#### TC-SC007: 缓存键前缀隔离 (P0)

**目的**: 验证不同 channel/kb 的缓存键隔离
**步骤**:

1. 使用不同 channel_id 和 kb_names
2. 验证缓存键前缀不同
   **期望**:

```python
prefix_a = cache._make_cache_key_prefix("ch_a", ["kb1"])
prefix_b = cache._make_cache_key_prefix("ch_b", ["kb1"])
assert prefix_a != prefix_b
```

### 6.4 嵌入器兼容性测试

#### TC-SC008: 多种嵌入器支持 (P1)

**目的**: 验证不同嵌入器接口的兼容性
**步骤**:

1. 测试 embed_text 和 embed 方法
2. 验证异步调用
   **期望**: 支持多种嵌入器接口

#### TC-SC009: 嵌入器不可用降级 (P1)

**目的**: 验证嵌入器不可用时跳过缓存
**步骤**:

1. 设置 capability_loader=None
2. Mock 嵌入器创建失败
   **期望**: 跳过缓存，继续正常流程

### 6.5 缓存统计测试

#### TC-SC010: 缓存命中率统计 (P2)

**目的**: 验证缓存命中率的准确统计
**步骤**:

1. 执行多次缓存命中和未命中
2. 调用 get_stats()
   **期望**:

```python
stats = cache.get_stats()
assert stats["hit_rate"] == hits / (hits + misses)
assert stats["cache_size"] <= max_cache_size
```

---

## 7. Web 搜索节点测试

### 7.1 Web 搜索集成测试

#### TC-WS001: Web 搜索结果集成 (P1)

**目的**: 验证 Web 搜索结果与现有结果的合并
**步骤**:

1. Mock web_search_client 返回结果
2. 设置现有 fused_results
3. 调用 WebSearchNode
   **期望**:

```python
# Web结果应该在前面
web_results = [r for r in state["fused_results"] if r["metadata"]["source"] == "web_search"]
assert len(web_results) > 0
assert web_results[0]["score"] > 0.5  # 高分排在前面
```

#### TC-WS002: Web 搜索失败处理 (P1)

**目的**: 验证 Web 搜索失败时的优雅处理
**步骤**:

1. Mock web_search_client 抛出异常
2. 调用 WebSearchNode
   **期望**: 不影响现有结果，无异常抛出

#### TC-WS003: Web 搜索结果格式化 (P1)

**目的**: 验证 Web 搜索结果的标准格式化
**步骤**:

1. Mock 返回包含 url、title、snippet 的结果
2. 验证格式化后的结构
   **期望**:

```python
web_chunk = web_results[0]
assert web_chunk["metadata"]["source"] == "web_search"
assert web_chunk["metadata"]["url"] is not None
assert web_chunk["content"] is not None
```

---

## 8. 错误注入测试

### 8.1 LLM 超时测试

#### TC-E001: LLM 调用超时处理 (P1)

**目的**: 验证 LLM 调用超时的处理
**步骤**:

1. Mock LLM 调用超时异常
2. 调用各个使用 LLM 的节点
   **期望**: 记录错误，使用回退策略

#### TC-E002: LLM 限流处理 (P1)

**目的**: 验证 LLM API 限流的处理
**步骤**:

1. Mock HTTP 429 错误
2. 验证重试机制
   **期望**: 适当延迟后重试

### 8.2 存储不可用测试

#### TC-E003: 向量数据库不可用 (P1)

**目的**: 验证向量数据库连接失败的处理
**步骤**:

1. Mock vector_client 连接异常
2. 调用 HybridRetriever
   **期望**: 降级到仅关键词检索

#### TC-E004: Elasticsearch 不可用 (P1)

**目的**: 验证 ES 不可用时的降级
**步骤**:

1. Mock keyword_client 异常
2. 调用 HybridRetriever
   **期望**: 降级到仅向量检索

### 8.3 重排序器失败测试

#### TC-E005: 重排序器模型加载失败 (P1)

**目的**: 验证重排序器不可用的处理
**步骤**:

1. Mock get_reranker 抛出异常
2. 调用 CrossEncoderReranker
   **期望**: 跳过重排序，使用原始分数

#### TC-E006: 重排序器推理失败 (P1)

**目的**: 验证重排序推理异常的处理
**步骤**:

1. Mock reranker.score 抛出异常
2. 调用 CrossEncoderReranker
   **期望**: 记录错误，保持原始排序

---

## 9. 指标监控测试

### 9.1 检索延迟指标

#### TC-M001: 检索延迟记录 (P2)

**目的**: 验证 retrieval_latency 指标的记录
**步骤**:

1. 调用 HybridRetriever
2. 验证延迟指标记录
   **期望**: 记录检索耗时

#### TC-M002: 各阶段延迟分解 (P2)

**目的**: 验证各检索阶段的延迟分解
**步骤**:

1. 监控向量检索、关键词检索、融合各阶段
2. 验证延迟分解
   **期望**: 各阶段延迟被单独记录

### 9.2 缓存命中率指标

#### TC-M003: 缓存命中率监控 (P2)

**目的**: 验证语义缓存命中率的监控
**步骤**:

1. 执行多次查询
2. 监控缓存命中率变化
   **期望**: 准确记录命中率趋势

#### TC-M004: 缓存大小监控 (P2)

**目的**: 验证缓存大小和清理的监控
**步骤**:

1. 监控缓存增长和清理
2. 验证大小指标
   **期望**: 缓存大小指标准确

---

## 10. 多租户越权测试

### 10.1 数据隔离验证

#### TC-MT001: 检索结果租户隔离 (P0)

**目的**: 验证检索结果严格按租户隔离
**步骤**:

1. 并发执行不同 channel_id 的检索
2. 验证结果不包含其他租户数据
   **期望**:

```python
# 结果只包含本租户数据
assert all(
    r.get("metadata", {}).get("channel_id") == current_channel_id
    for r in state["fused_results"]
)
```

#### TC-MT002: 缓存键租户隔离 (P0)

**目的**: 验证语义缓存按租户隔离
**步骤**:

1. 不同租户缓存相同查询
2. 验证缓存键不冲突
   **期望**: 不同租户的缓存独立

#### TC-MT003: 集合命名租户隔离 (P0)

**目的**: 验证向量集合按租户命名隔离
**步骤**:

1. 验证集合名称包含 channel_id
2. 确保不同租户使用不同集合
   **期望**: 集合名称格式正确且隔离

---

## 关键断言示例

### 路由映射断言

```python
def assert_routing_mapping(graph, intent_type, expected_node):
    """验证路由映射的标准断言"""
    state = {"intent": {"type": intent_type}}
    next_node = graph.get_next_node(state)
    assert next_node == expected_node
```

### 多租户隔离断言

```python
def assert_tenant_isolation(results_a, results_b, channel_a, channel_b):
    """验证多租户隔离的断言"""
    # 验证结果不交叉
    for result in results_a:
        channel = result.get("metadata", {}).get("channel_id")
        assert channel == channel_a or channel is None  # 允许遗留数据

    for result in results_b:
        channel = result.get("metadata", {}).get("channel_id")
        assert channel == channel_b or channel is None
```

### 缓存行为断言

```python
def assert_cache_behavior(state, expected_hit=True):
    """验证缓存行为的断言"""
    if expected_hit:
        assert state["cache_hit"] is True
        assert state["skip_retrieval"] is True
        assert "final_answer" in state
    else:
        assert state["cache_hit"] is False
        assert "_query_embedding" in state
```

### 引用完整性断言

```python
def assert_citation_integrity(citations, docs):
    """验证引用完整性的断言"""
    for citation in citations:
        assert "doc_id" in citation
        assert "content" in citation
        assert "chunk_id" in citation
        # 验证引用的文档确实存在
        chunk_ids = [d["id"] for d in docs]
        assert citation["chunk_id"] in chunk_ids
```

---

## 测试数据准备

### 最小可复现样例

1. **多租户查询**: 不同 channel_id 的相同查询
2. **语义相似查询**: 用于测试缓存命中
3. **多模态查询**: 表格、图片、文本混合查询
4. **Web 搜索查询**: 包含时效性关键词的查询
5. **长查询**: 测试嵌入和缓存性能
6. **多语言查询**: 中英混合查询

### Mock 数据生成器

```python
def generate_retrieval_state(
    channel_id="test_tenant",
    kb_names=["test_kb"],
    query="测试查询",
    intent_type="qa"
):
    """生成测试用检索状态"""
    return {
        "input_query": query,
        "channel_id": channel_id,
        "kb_names": kb_names,
        "intent": {"type": intent_type},
        "strategy_config": {
            "top_k": 10,
            "llm_provider": "mock",
            "llm_model": "mock-model"
        }
    }

def generate_mock_documents(count=5, channel_id="test"):
    """生成测试用文档"""
    return [
        {
            "id": f"doc_{i}",
            "content": f"测试内容 {i}",
            "metadata": {
                "channel_id": channel_id,
                "doc_id": f"file_{i}.pdf",
                "page_num": 1,
                "block_type": "text"
            },
            "score": 0.9 - i * 0.1
        }
        for i in range(count)
    ]
```

这套测试用例全面覆盖了检索管道的关键功能，特别关注多租户隔离、缓存机制、错误处理和性能监控等核心需求。
