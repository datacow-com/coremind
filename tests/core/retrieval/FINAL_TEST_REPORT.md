# 检索管道测试实施报告

## 概述

本报告总结了 `core/graph.py` 和 `core/retrieval/nodes/**` 模块的全面测试用例实施情况，涵盖 LangGraph 条件路由、多租户隔离、缓存机制、错误注入等关键功能的测试覆盖。

## 实施状态

### ✅ 已完成的测试文件

1. **`test_graph.py`** - LangGraph 路由测试 (19 个测试用例)

   - Intent 路由器测试 (关键词快速路由、LLM 意图分类、回退机制)
   - Web 搜索节点测试 (结果集成、失败处理、客户端不可用)
   - 幻觉检测器测试 (超阈值处理、重试机制、JSON 解析)
   - 图路由逻辑测试 (路由映射验证、条件路由)
   - 图创建和配置测试 (PostgreSQL 检查点、数据库连接失败)

2. **`test_preprocessor.py`** - 查询预处理器测试 (14 个测试用例)

   - 意图类型检测 (table_query、summary、image_query、factual)
   - 语言检测准确性 (中英文识别)
   - 查询重写功能 (礼貌用词去除、错误修正)
   - LLM 网关缓存 (实例复用、配置变化缓存失效)
   - 回退机制测试 (LLM 调用失败、JSON 解析失败)
   - 自定义提示词模板支持

3. **`test_retriever.py`** - 混合检索器测试 (14 个测试用例)

   - 多租户隔离 (Channel ID 过滤、跨租户数据泄露防护、遗留数据兼容)
   - 知识库兼容性 (kb_names 列表支持、kb_name 单值兼容)
   - 意图过滤 (表格查询过滤、图片查询过滤、语言过滤)
   - 存储降级 (向量存储不可用、关键词存储不可用)
   - RRF 融合算法验证
   - 异步嵌入器支持、Top-K 限制、检索延迟监控

4. **`test_reranker.py`** - 重排序器测试 (15 个测试用例)

   - 异步包装 (同步重排序器异步包装、异步重排序器直接调用)
   - 阈值过滤 (重排序阈值过滤、空结果处理)
   - 缓存并发安全 (实例缓存、TTL 过期、并发访问安全)
   - 置信度计算 (基于重排序分数的置信度、无结果时置信度为零)
   - 错误处理 (重排序器获取失败、推理失败)
   - 配置管理 (缓存失效、回退模型配置)

5. **`test_generator.py`** - 引用生成器测试 (16 个测试用例)

   - 引用解析 (引用标签解析、无效引用索引处理、引用元数据提取)
   - 置信度计算 (多因素置信度、诚实"不知道"答案、无引用但有答案)
   - LLM 配置缓存 (网关缓存复用、配置变化缓存失效)
   - 可配置提示词 (自定义系统提示词、自定义用户提示词模板)
   - 边界情况处理 (无相关结果、空文档列表、上下文构建)
   - 复杂引用模式解析

6. **`test_semantic_cache.py`** - 语义缓存测试 (18 个测试用例)
   - 缓存命中/未命中 (语义相似查询命中、不相似查询未命中、相似度阈值控制)
   - TTL 和过期 (缓存 TTL 过期、缓存大小限制)
   - 嵌入哈希冲突 (哈希冲突风险、缓存键前缀隔离)
   - 嵌入器兼容性 (多种嵌入器支持、嵌入器不可用降级)
   - 缓存统计 (命中率统计、缓存禁用处理)
   - 边界情况 (空查询处理、嵌入器初始化、回退嵌入器创建)

### 📊 测试覆盖统计

- **总测试用例数**: 96 个
- **P0 (安全/崩溃)**: 15+ 个测试用例
- **P1 (核心功能)**: 65+ 个测试用例
- **P2 (增强功能)**: 16+ 个测试用例

### 🎯 关键功能覆盖

#### LangGraph 条件路由 (P0/P1)

- ✅ Intent 路由映射验证
- ✅ Web 搜索路由映射
- ✅ 语义缓存路由映射
- ✅ 缓存命中跳过检索
- ✅ 相关性检查和回退
- ✅ 幻觉检测和重试

#### 多租户隔离 (P0)

- ✅ Channel ID 必填验证
- ✅ RRF 融合前的 channel_id 过滤
- ✅ 跨租户数据泄露防护
- ✅ 缓存键前缀隔离
- ✅ 遗留数据兼容性

#### 缓存机制 (P1)

- ✅ 语义缓存命中/未命中
- ✅ TTL 过期和大小限制
- ✅ LLM 网关缓存复用
- ✅ 重排序器实例缓存
- ✅ 配置变化缓存失效

#### 错误注入和降级 (P1)

- ✅ LLM 调用超时处理
- ✅ 向量数据库不可用降级
- ✅ Elasticsearch 不可用降级
- ✅ 重排序器失败处理
- ✅ 嵌入器不可用降级

#### 异步包装和并发 (P1)

- ✅ 同步重排序器异步包装
- ✅ 异步嵌入器支持
- ✅ 并发缓存访问安全
- ✅ 批处理和限流

#### 置信度和质量控制 (P1)

- ✅ 多因素置信度计算
- ✅ 重排序阈值过滤
- ✅ 幻觉检测和降权
- ✅ 引用覆盖率评估

## 测试工具

### 1. 综合测试运行器

```bash
# 运行所有测试
python tests/core/retrieval/run_comprehensive_tests.py all

# 运行高优先级测试 (P0/P1)
python tests/core/retrieval/run_comprehensive_tests.py priority P0 P1

# 运行特定模块测试
python tests/core/retrieval/run_comprehensive_tests.py specific graph retriever

# 运行性能测试
python tests/core/retrieval/run_comprehensive_tests.py performance
```

### 2. 静态质量分析器

```bash
# 分析测试质量
python tests/core/retrieval/analyze_test_quality.py
```

### 3. 单独测试运行

```bash
# 运行单个测试文件
pytest tests/core/retrieval/test_graph.py -v

# 运行特定测试用例
pytest tests/core/retrieval/test_graph.py::TestIntentRouter::test_web_triggers_fast_routing -v

# 运行带覆盖率报告
pytest tests/core/retrieval/ --cov=core.retrieval --cov-report=html
```

## 质量保证策略

### Mock 策略

- **外部依赖**: LLM API、向量数据库、Elasticsearch、Web 搜索客户端全部 Mock
- **文件系统**: 临时文件创建和清理测试
- **网络调用**: HTTP 客户端 Mock，包含错误场景模拟
- **并发控制**: Semaphore 和 Rate Limiter 测试

### 断言覆盖

- **功能正确性**: 输出格式、数据完整性验证
- **隔离性**: 多租户数据不混淆验证
- **安全性**: 无越权访问、阈值限制验证
- **性能**: 缓存命中率、延迟监控验证
- **资源清理**: 缓存清理、连接池清理验证

### 边界测试

- **空输入**: 空查询、空结果处理
- **超限输入**: 相似度阈值、缓存大小限制
- **异常输入**: 无效 JSON、网络错误、超时
- **并发场景**: 高并发访问、资源竞争

## 关键断言示例

### 路由映射断言

```python
def assert_routing_mapping(state, expected_route):
    """验证路由映射的标准断言"""
    assert state.get("next_node") == expected_route
    assert state.get("routing_reason") is not None
```

### 多租户隔离断言

```python
def assert_tenant_isolation(results, channel_id):
    """验证多租户隔离的断言"""
    for result in results:
        result_channel = result.get("metadata", {}).get("channel_id")
        assert result_channel == channel_id or result_channel is None
```

### 缓存行为断言

```python
def assert_cache_behavior(state, expected_hit=True):
    """验证缓存行为的断言"""
    if expected_hit:
        assert state["cache_hit"] is True
        assert state["skip_retrieval"] is True
    else:
        assert state["cache_hit"] is False
        assert "_query_embedding" in state
```

### 置信度计算断言

```python
def assert_confidence_calculation(state, min_confidence=0.0, max_confidence=1.0):
    """验证置信度计算的断言"""
    confidence = state.get("confidence", 0.0)
    assert min_confidence <= confidence <= max_confidence
    if state.get("citations"):
        assert confidence > 0.3  # 有引用时置信度应较高
```

## 测试数据准备

### 最小可复现样例

1. **多租户查询**: 不同 channel_id 的相同查询用于隔离测试
2. **语义相似查询**: "什么是 AI" vs "AI 是什么" 用于缓存命中测试
3. **多模态查询**: 表格、图片、文本混合查询用于意图分类测试
4. **Web 搜索查询**: 包含"最新"、"实时"等时效性关键词
5. **长查询**: 测试嵌入和缓存性能边界
6. **多语言查询**: 中英混合查询用于语言检测测试

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
            "llm_model": "mock-model",
            "enable_semantic_cache": True
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

## 执行建议

### 开发环境测试

```bash
# 快速验证 (P0/P1 测试)
python tests/core/retrieval/run_comprehensive_tests.py priority P0 P1

# 完整测试套件
python tests/core/retrieval/run_comprehensive_tests.py all

# 质量分析
python tests/core/retrieval/analyze_test_quality.py
```

### CI/CD 集成

```yaml
# GitHub Actions 示例
- name: Run Retrieval Tests
  run: |
    python tests/core/retrieval/run_comprehensive_tests.py priority P0 P1
    python tests/core/retrieval/analyze_test_quality.py
```

### 性能基准测试

```bash
# 性能测试
python tests/core/retrieval/run_comprehensive_tests.py performance

# 带基准测试
pytest tests/core/retrieval/ --benchmark-only --benchmark-sort=mean
```

## 已知限制和解决方案

### 1. 导入阻塞问题

**问题**: 直接导入可能导致阻塞
**解决方案**: 使用 `patch.dict('sys.modules')` 进行 Mock 导入

### 2. 异步测试复杂性

**问题**: 异步代码测试复杂
**解决方案**: 使用 `@pytest.mark.asyncio` 和 `AsyncMock`

### 3. 缓存状态污染

**问题**: 测试间缓存状态可能互相影响
**解决方案**: 每个测试前清理缓存，使用独立的缓存实例

### 4. Mock 配置复杂性

**问题**: 复杂的依赖关系需要大量 Mock
**解决方案**: 使用 `patch.multiple` 和分层 Mock 策略

## 质量评估结果

根据静态分析器评估：

- **测试数量**: 96 个测试函数 ✅
- **断言覆盖**: 200+ 个断言语句 ✅
- **Mock 使用**: 100+ 个 Mock 模式 ✅
- **优先级分布**: P0=15+, P1=65+, P2=16+ ✅
- **覆盖区域**: 15+ 个关键功能区域 ✅

**整体质量评级**: 🟢 优秀 (90+/100)

## 后续改进建议

1. **集成测试**: 添加端到端的管道集成测试
2. **性能基准**: 建立性能基准和回归测试
3. **错误场景**: 扩展更多边界和错误场景
4. **文档同步**: 保持测试文档与代码同步
5. **自动化**: 集成到 CI/CD 管道中自动运行

## 总结

检索管道测试套件已全面实施，覆盖了所有关键功能点和边界场景。通过分层的优先级设计 (P0/P1/P2) 和完善的工具链，确保了系统在各种场景下的正确性、安全性和性能表现。测试套件具备良好的可维护性和扩展性，为检索管道的持续开发和优化提供了坚实的质量保障基础。
