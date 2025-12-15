# Requirements Document

## Introduction

本需求文档定义了 OmniRAG 垂直领域增强第一阶段（Phase 1）的功能需求。Phase 1 的核心目标是搭建多云算力基础设施，包括成本估算与预算控制、增强现有 LLM Gateway，并通过真实 API 调用验证系统的正确性。

本阶段遵循「真实数据驱动开发」原则，拒绝空壳 Mock，确保所有功能都经过真实 API 调用验证。

**重要架构决策：** 经过对现有代码的分析，本需求**不创建新的 `core/compute/` 模块**，而是增强现有的 `core/llm/` 模块，避免重复造轮子。

## Glossary

- **Provider**: 云服务提供商，如 DashScope（阿里云百炼）、火山方舟、Azure OpenAI、DeepSeek 等
- **LLM Gateway**: 现有的 LLM 网关（`core/llm/gateway.py`），统一的模型调用入口，已有熔断/降级/用量记录功能
- **Cost Tracker**: 成本追踪器，记录每次 API 调用的成本到数据库（新增到 `core/llm/`）
- **Cost Estimator**: 成本估算器，在调用前预估成本（新增到 `core/llm/`）
- **Budget Config**: 预算配置，支持全局、Channel 级、用户级预算控制
- **Circuit Breaker**: 熔断器，当 Provider 连续失败时自动熔断（现有 Gateway 已实现）
- **Failover Chain**: 故障转移链，当主 Provider 不可用时自动切换到备选 Provider
- **Routing Strategy**: 路由策略，包括 cost_first（成本优先）、performance_first（性能优先）、balanced（平衡）
- **VLM**: Vision Language Model，视觉语言模型，用于图片理解

## Requirements

### Requirement 1: 现有实现分析

**User Story:** As a developer, I want to understand the existing implementation before writing new code, so that I can avoid duplicating functionality and ensure proper integration.

#### Acceptance Criteria

1. WHEN a developer starts Phase 1 development THEN the system documentation SHALL include a complete analysis of `core/llm/gateway.py` with class diagrams showing existing Provider loading, circuit breaker, and usage recording mechanisms
2. WHEN analyzing existing code THEN the documentation SHALL identify that `core/llm/gateway.py` already has DB-driven Provider loading via `_get_model_config()`, circuit breaker via `_cb_*` methods, and usage recording via `_record_usage()`
3. WHEN analyzing `core/embedding/provider_embedder.py` THEN the documentation SHALL identify existing LRU+TTL cache mechanism and DB-driven Provider configuration
4. WHEN analyzing `server/models.py` THEN the documentation SHALL identify existing `Provider` and `ModelConfig` ORM models that can be extended

### Requirement 2: 数据库 Schema 扩展（非新建）

**User Story:** As a system architect, I want to extend the existing database schema to support cost tracking and budget control, so that the system maintains data consistency while adding new functionality.

#### Acceptance Criteria

1. WHEN extending the Provider model THEN the `providers` table SHALL be extended with new fields: priority (INTEGER), endpoints (JSONB), rate_limits (JSONB), is_healthy (BOOLEAN), circuit_breaker_failures (INTEGER), circuit_breaker_open_until (TIMESTAMP)
2. WHEN the system records API call costs THEN a new `compute_cost_records` table SHALL be created with fields for request_id, channel_id, user_id, provider_id, model_id, task_type, token counts, cost_usd, latency_ms, cached status, success status, and error_message
3. WHEN the system manages budgets THEN a new `budget_configs` table SHALL be created supporting global, channel-level, and user-level budget limits with alert and hard-stop thresholds
4. WHEN the system prepares for future phases THEN a new `domain_configs` table SHALL be created with fields for ontology, visual_schema, narrative_schema, and interpretation_rules
5. WHEN querying cost data THEN the system SHALL provide `daily_cost_summary` and `channel_cost_summary` views for efficient aggregation

### Requirement 3: Provider 配置扩展

**User Story:** As a developer, I want to add new cloud Providers to the existing configuration system, so that the system can leverage multiple cloud services for cost optimization and reliability.

#### Acceptance Criteria

1. WHEN configuring a new Provider THEN the existing `core/llm/provider_config.py` SHALL be extended to support DashScope, 火山方舟 (Volcengine), Azure OpenAI, and DeepSeek with their respective endpoints and model configurations
2. WHEN a Provider is configured THEN the configuration SHALL include base_url, api_key_env, models with cost_per_1k_tokens, context_length, category (domestic/foreign), and priority
3. WHEN adding Provider data THEN the existing `providers` and `model_configs` database tables SHALL be populated with the new Provider information
4. WHEN validating Provider configuration THEN the system SHALL check for required environment variables and report missing configurations using the existing `validate_provider()` function

### Requirement 4: LLM Gateway 增强

**User Story:** As a developer, I want the existing LLM Gateway to support Provider routing and cost tracking, so that the system can automatically select the best Provider and track costs.

#### Acceptance Criteria

1. WHEN the Gateway receives a request THEN the Gateway SHALL support routing strategies: cost_first, performance_first, and balanced via a new optional `routing_strategy` parameter
2. WHEN the primary Provider fails THEN the existing circuit breaker mechanism SHALL be enhanced to support automatic failover to the next Provider in a configurable failover_chain
3. WHEN an API call completes THEN the Gateway SHALL record the cost to the `compute_cost_records` table via a new CostTracker class in `core/llm/cost_tracker.py`
4. WHEN an API call is initiated THEN the Gateway SHALL check the budget via CostTracker and reject or degrade the request if budget is exceeded
5. WHEN the Gateway is enhanced THEN all existing API calls SHALL continue to work without modification (backward compatibility with existing `chat()` method signature)

### Requirement 5: 成本追踪与预算控制

**User Story:** As a system administrator, I want to track API costs and control budgets, so that I can manage cloud spending effectively.

#### Acceptance Criteria

1. WHEN an API call completes THEN the CostTracker (in `core/llm/cost_tracker.py`) SHALL record request_id, provider_id, model_id, task_type, input_tokens, output_tokens, image_count, cost_usd, latency_ms, cached status, and success status
2. WHEN querying daily costs THEN the CostTracker SHALL return the sum of cost_usd for the specified date and optional channel_id
3. WHEN checking budget THEN the CostTracker SHALL compare current daily cost against the configured daily_limit and return allowed status and remaining budget
4. WHEN daily cost exceeds hard_stop_threshold THEN the system SHALL reject new requests for that scope
5. WHEN daily cost exceeds alert_threshold THEN the system SHALL log a warning (future: send notification)

### Requirement 6: 真实 API 调用验证

**User Story:** As a QA engineer, I want to verify that all Providers work with real API calls, so that I can ensure the system functions correctly in production.

#### Acceptance Criteria

1. WHEN running integration tests THEN at least 2 cloud Providers SHALL complete real Chat API calls successfully
2. WHEN running VLM tests THEN the system SHALL process at least 10 real test images using DashScope qwen-vl-plus or equivalent
3. WHEN running Embedding tests THEN the system SHALL generate real embeddings for test texts and verify dimensions
4. WHEN testing failover THEN the system SHALL automatically switch to a fallback Provider when the primary is unavailable
5. WHEN testing cost tracking THEN the database SHALL contain cost records for all real API calls

### Requirement 7: core/llm 模块增强（非新建 core/compute）

**User Story:** As a developer, I want to enhance the existing core/llm module with cost tracking and routing capabilities, so that the system maintains architectural consistency while adding new functionality.

#### Acceptance Criteria

1. WHEN adding cost tracking THEN the system SHALL add `core/llm/cost_tracker.py` to the existing core/llm module (NOT create a new core/compute module)
2. WHEN adding cost estimation THEN the system SHALL add `core/llm/cost_estimator.py` to the existing core/llm module
3. WHEN the LLMGateway is enhanced THEN it SHALL integrate with CostTracker for automatic cost recording
4. WHEN the LLMGateway selects a Provider THEN it SHALL use the existing database-driven Provider model with enhanced routing_strategy support
5. WHEN a Provider is unhealthy THEN the existing circuit breaker in LLMGateway SHALL mark it as unhealthy and trigger failover using the existing `_cb_*` methods

### Requirement 8: 集成与回归测试

**User Story:** As a developer, I want comprehensive integration tests and regression tests, so that I can ensure the new functionality works correctly and existing functionality is not broken.

#### Acceptance Criteria

1. WHEN running E2E tests THEN the `tests/integration/test_phase1_e2e.py` SHALL verify Chat with cost tracking, cost-first routing, VLM real image processing, failover chain, and budget control
2. WHEN running regression tests THEN all existing tests in tests/core/ and tests/server/ SHALL pass
3. WHEN preparing test data THEN the data/samples/ directory SHALL contain at least 10 test images and 5 text samples
4. WHEN the Phase 1 is complete THEN the code coverage for new code SHALL exceed 80%

---

## Architecture Decision Record

### ADR-001: 不创建 core/compute 模块

**状态：** 已决定

**背景：** PHASE1 原始文档提议创建新的 `core/compute/` 模块来管理多云 Provider。

**决定：** 不创建 `core/compute/` 模块，而是增强现有 `core/llm/` 模块。

**理由：**

1. `core/llm/gateway.py` 已有 DB 驱动的 Provider 加载、熔断/降级、用量记录功能
2. `core/embedding/provider_embedder.py` 已有 DB 驱动的 Provider 配置和缓存机制
3. `server/models.py` 已有 Provider 和 ModelConfig ORM 模型
4. 创建新模块会导致重复造轮子和架构不一致

**影响：**

- 新增文件：`core/llm/cost_tracker.py`, `core/llm/cost_estimator.py`
- 修改文件：`core/llm/gateway.py`, `core/llm/provider_config.py`, `server/models.py`
- 不创建：`core/compute/` 目录及其所有文件

### ADR-002: 扩展现有数据库表而非新建

**状态：** 已决定

**背景：** PHASE1 原始文档提议创建新的 `compute_providers` 表。

**决定：** 扩展现有 `providers` 表，新建 `compute_cost_records` 和 `budget_configs` 表。

**理由：**

1. 现有 `providers` 表已有 Provider 基本信息
2. 现有 `model_configs` 表已有模型配置
3. 新建重复表会导致数据不一致

**影响：**

- 扩展：`providers` 表添加 priority, endpoints, rate_limits, is_healthy 等字段
- 新建：`compute_cost_records` 表（成本记录）
- 新建：`budget_configs` 表（预算配置）
- 新建：`domain_configs` 表（为 Phase 2+ 预留）
