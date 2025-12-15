# Implementation Plan

- [x] 1. 现有实现分析与文档

  - [x] 1.1 分析 core/llm/gateway.py 并创建类图

    - 分析现有 Provider 加载机制 `_get_model_config()`
    - 分析熔断/降级逻辑 `_cb_allowed()`, `_cb_on_fail()`, `_cb_on_success()`
    - 分析用量记录 `_record_usage()`
    - 输出 Mermaid 类图到 `docs/tech/phase1_existing_analysis.md`
    - _Requirements: 1.1, 1.2_

  - [x] 1.2 分析 core/embedding/provider_embedder.py

    - 分析 DB 驱动的 Provider 配置
    - 分析 LRU+TTL 缓存机制
    - 记录可复用的模式
    - _Requirements: 1.3_

  - [x] 1.3 分析 server/models.py 现有模型
    - 分析 Provider 和 ModelConfig ORM 模型
    - 确定需要扩展的字段
    - _Requirements: 1.4_

- [x] 2. 数据库 Schema 扩展

  - [x] 2.1 扩展 Provider 模型

    - 在 `server/models.py` 中为 Provider 添加新字段：priority, endpoints, rate_limits, is_healthy, circuit_breaker_failures, circuit_breaker_open_until
    - _Requirements: 2.1_

  - [x] 2.2 Write property test for cost record round trip

    - **Property 1: Cost Record Round Trip**
    - **Validates: Requirements 2.2, 5.1**

  - [x] 2.3 创建 ComputeCostRecord 模型

    - 在 `server/models.py` 中添加 ComputeCostRecord 类
    - 包含 request_id, channel_id, user_id, provider_id, model_id, task_type, input_tokens, output_tokens, image_count, cost_usd, latency_ms, cached, success, error_message, created_at
    - _Requirements: 2.2_

  - [x] 2.4 创建 BudgetConfig 模型

    - 在 `server/models.py` 中添加 BudgetConfig 类
    - 包含 scope, scope_id, daily_limit, monthly_limit, alert_threshold, hard_stop_threshold, is_active
    - _Requirements: 2.3_

  - [x] 2.5 创建 DomainConfig 模型（Phase 2+ 预留）

    - 在 `server/models.py` 中添加 DomainConfig 类
    - 包含 ontology, visual_schema, narrative_schema, interpretation_rules, gpu_requirements
    - _Requirements: 2.4_

  - [x] 2.6 创建数据库迁移脚本

    - 创建 `core/storage/migrations/002_compute_infrastructure.sql`
    - 包含所有新表和扩展字段的 SQL
    - 创建 daily_cost_summary 和 channel_cost_summary 视图
    - _Requirements: 2.5_

  - [x] 2.7 Write property test for daily cost aggregation
    - **Property 2: Daily Cost Aggregation Consistency**
    - **Validates: Requirements 2.5, 5.2**

- [x] 3. Checkpoint - 确保数据库迁移成功

  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 成本追踪器实现

  - [x] 4.1 创建 CostRecord 数据类

    - 在 `core/llm/cost_tracker.py` 中创建 CostRecord dataclass
    - _Requirements: 5.1_

  - [x] 4.2 实现 CostTracker.track() 方法

    - 实现异步写入数据库逻辑
    - _Requirements: 4.3, 5.1_

  - [x] 4.3 实现 CostTracker.get_daily_cost() 方法

    - 实现按日期和可选 channel_id 查询成本
    - _Requirements: 5.2_

  - [x] 4.4 Write property test for budget check correctness

    - **Property 3: Budget Check Correctness**
    - **Validates: Requirements 5.3, 5.4**

  - [x] 4.5 实现 CostTracker.check_budget() 方法

    - 实现预算检查逻辑
    - 返回 (allowed, remaining) 元组
    - _Requirements: 5.3, 5.4_

  - [x] 4.6 Write unit tests for CostTracker
    - 测试 track() 创建记录
    - 测试 get_daily_cost() 返回正确值
    - 测试 check_budget() 在不同场景下的行为
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 5. 成本估算器实现

  - [x] 5.1 创建 CostEstimator 类

    - 在 `core/llm/cost_estimator.py` 中创建类
    - 包含 DEFAULT_COSTS 配置
    - _Requirements: 7.2_

  - [x] 5.2 实现 estimate() 方法

    - 根据 provider_id, model_id, tokens 计算成本
    - _Requirements: 7.2_

  - [x] 5.3 实现 get_cheapest_provider() 方法

    - 返回成本最低的 provider 和 model
    - _Requirements: 4.1_

  - [x] 5.4 Write unit tests for CostEstimator
    - 测试 estimate() 返回正确成本
    - 测试 get_cheapest_provider() 返回最便宜的选项
    - _Requirements: 7.2_

- [x] 6. Checkpoint - 确保成本追踪和估算功能正常

  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Provider 配置扩展

  - [x] 7.1 扩展 provider_config.py

    - 添加 ENHANCED_PROVIDER_CONFIGS 字典
    - 包含 volcengine, azure, deepseek 配置
    - _Requirements: 3.1, 3.2_

  - [x] 7.2 Write property test for provider configuration completeness

    - **Property 4: Provider Configuration Completeness**
    - **Validates: Requirements 3.2**

  - [x] 7.3 Write property test for environment variable validation

    - **Property 5: Environment Variable Validation**
    - **Validates: Requirements 3.4**

  - [x] 7.4 更新 REQUIRED_ENV 映射

    - 添加新 Provider 的环境变量要求
    - _Requirements: 3.4_

  - [x] 7.5 创建数据库种子数据
    - 创建脚本填充 providers 和 model_configs 表
    - _Requirements: 3.3_

- [x] 8. LLM Gateway 增强

  - [x] 8.1 添加新的构造函数参数

    - 添加 routing_strategy, channel_id, enable_cost_tracking 参数
    - 保持向后兼容
    - _Requirements: 4.1, 4.5_

  - [x] 8.2 Write property test for routing strategy selection

    - **Property 6: Routing Strategy Selection**
    - **Validates: Requirements 4.1**

  - [x] 8.3 实现 \_select_provider() 方法

    - 根据 routing_strategy 选择 Provider
    - 支持 cost_first, performance_first, balanced
    - _Requirements: 4.1_

  - [x] 8.4 Write property test for failover chain correctness

    - **Property 7: Failover Chain Correctness**
    - **Validates: Requirements 4.2, 6.4, 7.5**

  - [x] 8.5 增强故障转移逻辑

    - 在现有 _cb_\* 方法基础上增强
    - 支持 failover_chain 配置
    - _Requirements: 4.2_

  - [x] 8.6 Write property test for cost tracking integration

    - **Property 8: Cost Tracking Integration**
    - **Validates: Requirements 4.3, 6.5, 7.3**

  - [x] 8.7 集成成本追踪

    - 在 chat() 方法中集成 CostTracker
    - 调用完成后记录成本
    - _Requirements: 4.3, 7.3_

  - [x] 8.8 Write property test for budget enforcement

    - **Property 9: Budget Enforcement**
    - **Validates: Requirements 4.4**

  - [x] 8.9 实现预算检查

    - 在调用前检查预算
    - 超预算时抛出 BudgetExceededError
    - _Requirements: 4.4_

  - [x] 8.10 Write property test for backward compatibility
    - **Property 10: Backward Compatibility**
    - **Validates: Requirements 4.5**

- [x] 9. Checkpoint - 确保 Gateway 增强功能正常

  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. 错误处理

  - [x] 10.1 创建自定义异常类

    - 创建 BudgetExceededError
    - 创建 ProviderUnavailableError
    - _Requirements: 4.4, 4.2_

  - [x] 10.2 Write unit tests for error handling
    - 测试 BudgetExceededError 在预算超限时抛出
    - 测试 ProviderUnavailableError 在所有 Provider 失败时抛出
    - _Requirements: 4.4, 4.2_

- [x] 11. 集成测试

  - [x] 11.1 创建真实 API 测试文件

    - 创建 `tests/integration/test_provider_real_api.py`
    - 包含 DashScope, DeepSeek 真实 API 测试
    - _Requirements: 6.1_

  - [x] 11.2 创建 VLM 真实图片测试

    - 测试处理 10+ 张真实图片
    - _Requirements: 6.2_

  - [x] 11.3 创建 Embedding 真实测试

    - 测试生成真实 embeddings
    - _Requirements: 6.3_

  - [x] 11.4 创建故障转移测试

    - 测试 Provider 故障时自动切换
    - _Requirements: 6.4_

  - [x] 11.5 创建成本追踪验证测试
    - 验证数据库中存在成本记录
    - _Requirements: 6.5_

- [x] 12. 测试数据准备

  - [x] 12.1 准备测试图片

    - 在 `data/samples/` 目录准备 10+ 张测试图片
    - _Requirements: 8.3_

  - [x] 12.2 准备测试文本
    - 准备 5+ 个不同领域的文本片段
    - _Requirements: 8.3_

- [x] 13. E2E 测试

  - [x] 13.1 创建 E2E 测试文件
    - 创建 `tests/integration/test_phase1_e2e.py`
    - 包含 Chat + 成本追踪、成本优先路由、VLM 处理、故障转移、预算控制测试
    - _Requirements: 8.1_

- [x] 14. 回归测试

  - [x] 14.1 运行现有测试
    - 运行 `pytest tests/core/ -v`
    - 运行 `pytest tests/server/ -v`
    - 确保所有现有测试通过
    - _Requirements: 8.2_

- [x] 15. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
