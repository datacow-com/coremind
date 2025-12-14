# Requirements Document

## Introduction

本需求文档定义了 `core/state.py` 中 `StrategyConfig` 配置兼容性和多租户 `channel_id` 验证的测试需求。重点覆盖：

1. 平铺/嵌套配置字段的兼容性和 `*_effective` 属性的正确计算
2. 多租户场景下 `channel_id` 缺失时各组件的行为验证

## Glossary

- **StrategyConfig**: 策略配置 Pydantic 模型，支持 UI 注入的配置参数
- **平铺配置 (Flat Config)**: 直接在顶层定义的配置字段，如 `chunking_mode`
- **嵌套配置 (Nested Config)**: 通过嵌套对象定义的配置字段，如 `chunking.mode`
- **Effective 属性**: 计算属性，根据优先级规则返回最终生效值
- **channel_id**: 多租户隔离标识符，用于数据隔离
- **IngestState**: 摄入管道状态 TypedDict
- **RetrievalState**: 检索管道状态 TypedDict

## Requirements

### Requirement 1

**User Story:** As a developer, I want StrategyConfig to support both flat and nested configuration patterns, so that I can use either format from UI or config files.

#### Acceptance Criteria

1. WHEN only flat chunking fields are provided (chunking_mode, chunk_size, chunk_overlap, preserve_tables) THEN the StrategyConfig SHALL use flat values for effective properties
2. WHEN only nested chunking object is provided THEN the StrategyConfig SHALL use nested values for effective properties
3. WHEN both flat and nested chunking fields are provided THEN the StrategyConfig SHALL prioritize flat values over nested values for effective properties
4. WHEN neither flat nor nested chunking fields are provided THEN the StrategyConfig SHALL use default values from ChunkingStrategy for effective properties

### Requirement 2

**User Story:** As a developer, I want effective properties to correctly compute final values, so that downstream components receive consistent configuration.

#### Acceptance Criteria

1. WHEN chunking_mode_effective is accessed THEN the StrategyConfig SHALL return flat chunking_mode if set, otherwise nested chunking.mode
2. WHEN chunk_size_effective is accessed THEN the StrategyConfig SHALL return flat chunk_size if set, otherwise nested chunking.chunk_size
3. WHEN chunk_overlap_effective is accessed THEN the StrategyConfig SHALL return flat chunk_overlap if set, otherwise nested chunking.chunk_overlap
4. WHEN preserve_tables_effective is accessed THEN the StrategyConfig SHALL return flat preserve_tables if not None, otherwise nested chunking.preserve_tables
5. WHEN flat field is explicitly set to a falsy but valid value (e.g., chunk_overlap=0) THEN the StrategyConfig SHALL use the flat value, not fall back to nested

### Requirement 3

**User Story:** As a system administrator, I want channel_id to be required for multi-tenant operations, so that data isolation is enforced.

#### Acceptance Criteria

1. WHEN IngestState is created without channel_id THEN the system SHALL raise a validation error or type error
2. WHEN RetrievalState is created without channel_id THEN the system SHALL raise a validation error or type error
3. WHEN a retrieval component receives state without channel_id THEN the component SHALL reject the request or emit a warning
4. WHEN a multimodal retriever search is called without channel_id THEN the retriever SHALL raise an error

### Requirement 4

**User Story:** As a developer, I want to verify that algorithm components enforce channel_id, so that multi-tenant isolation is guaranteed.

#### Acceptance Criteria

1. WHEN GraphLightState is used without channel_id THEN the algorithm SHALL fail with a clear error message
2. WHEN RaptorLightState is used without channel_id THEN the algorithm SHALL fail with a clear error message
3. WHEN algorithm collect_texts is called with empty channel_id THEN the function SHALL reject the request

### Requirement 5

**User Story:** As a QA engineer, I want comprehensive test coverage for edge cases, so that configuration handling is robust.

#### Acceptance Criteria

1. WHEN StrategyConfig receives invalid chunking_mode value THEN the config SHALL raise a validation error
2. WHEN StrategyConfig receives negative chunk_size THEN the config SHALL either raise an error or use default
3. WHEN mixed valid and invalid flat/nested fields are provided THEN the config SHALL validate all fields correctly
4. WHEN serializing StrategyConfig to dict THEN the output SHALL include both flat and nested fields for round-trip compatibility
