# Design Document: StrategyConfig 和 Multi-Tenant 测试

## Overview

本设计文档定义了 `core/state.py` 中 `StrategyConfig` 配置兼容性和多租户 `channel_id` 验证的测试方案。测试将使用 pytest 和 hypothesis 进行属性测试。

## Architecture

```
tests/core/state/
├── test_strategy_config.py      # StrategyConfig 平铺/嵌套兼容性测试
├── test_effective_properties.py # *_effective 属性计算测试
├── test_channel_id_validation.py # channel_id 多租户验证测试
└── conftest.py                  # 共享 fixtures 和 generators
```

## Components and Interfaces

### 1. StrategyConfig 测试组件

测试 `StrategyConfig` Pydantic 模型的配置兼容性：

```python
# 测试输入类型
FlatConfig = {
    "chunking_mode": Literal["fixed", "semantic", "layout_aware", "table_first"] | None,
    "chunk_size": int | None,
    "chunk_overlap": int | None,
    "preserve_tables": bool | None,
}

NestedConfig = {
    "chunking": ChunkingStrategy,
}

# 测试输出验证
EffectiveValues = {
    "chunking_mode_effective": str,
    "chunk_size_effective": int,
    "chunk_overlap_effective": int,
    "preserve_tables_effective": bool,
}
```

### 2. Channel ID 验证组件

测试多租户隔离的 `channel_id` 强制逻辑：

```python
# 测试目标
- IngestState TypedDict
- RetrievalState TypedDict
- MultimodalRetriever.search() 方法
- GraphLightState / RaptorLightState
```

## Data Models

### 测试数据生成策略

```python
from hypothesis import strategies as st

# ChunkingStrategy 生成器
chunking_strategy = st.builds(
    ChunkingStrategy,
    mode=st.sampled_from(["fixed", "semantic", "layout_aware", "table_first"]),
    chunk_size=st.integers(min_value=64, max_value=4096),
    chunk_overlap=st.integers(min_value=0, max_value=512),
    preserve_tables=st.booleans(),
)

# 平铺配置生成器
flat_config = st.fixed_dictionaries({
    "chunking_mode": st.sampled_from(["fixed", "semantic", "layout_aware", "table_first"]),
    "chunk_size": st.integers(min_value=64, max_value=4096),
    "chunk_overlap": st.integers(min_value=0, max_value=512),
    "preserve_tables": st.booleans(),
})

# channel_id 生成器
channel_id = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=64,
)
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

### Property 1: Flat config priority over nested

_For any_ valid flat configuration values and any valid nested ChunkingStrategy, when both are provided to StrategyConfig, the effective properties SHALL return the flat values.

**Validates: Requirements 1.1, 1.3, 2.1-2.4**

### Property 2: Nested fallback when flat is None

_For any_ valid ChunkingStrategy, when flat fields are all None, the effective properties SHALL return the nested ChunkingStrategy values.

**Validates: Requirements 1.2, 2.1-2.4**

### Property 3: Falsy values are not treated as unset

_For any_ StrategyConfig where flat chunk_overlap is explicitly 0, the chunk_overlap_effective SHALL return 0, not the nested default.

**Validates: Requirements 2.5**

### Property 4: Serialization round-trip preserves effective values

_For any_ valid StrategyConfig, serializing to dict via `model_dump()` and reconstructing SHALL preserve all effective property values.

**Validates: Requirements 5.4**

### Property 5: Invalid chunking_mode raises validation error

_For any_ string that is not in ["fixed", "semantic", "layout_aware", "table_first"], creating StrategyConfig with that chunking_mode SHALL raise a Pydantic ValidationError.

**Validates: Requirements 5.1**

## Error Handling

### 配置验证错误

| 错误场景           | 预期行为                            | 错误类型                 |
| :----------------- | :---------------------------------- | :----------------------- |
| 无效 chunking_mode | 抛出 ValidationError                | pydantic.ValidationError |
| 负数 chunk_size    | 接受（Pydantic 不限制）或自定义验证 | -                        |
| 缺少 channel_id    | 组件拒绝或告警                      | ValueError / TypeError   |

### 多租户错误

| 错误场景                      | 预期行为               | 错误类型   |
| :---------------------------- | :--------------------- | :--------- |
| search() 缺 channel_id        | TypeError (必需参数)   | TypeError  |
| Algorithm state 缺 channel_id | KeyError 或 ValueError | KeyError   |
| 空字符串 channel_id           | 组件应拒绝             | ValueError |

## Testing Strategy

### 属性测试 (Property-Based Testing)

使用 **hypothesis** 库进行属性测试：

```python
# requirements-dev.txt
hypothesis>=6.0.0
```

每个属性测试配置运行至少 100 次迭代：

```python
from hypothesis import settings

@settings(max_examples=100)
@given(...)
def test_property_xxx(...):
    ...
```

### 单元测试

单元测试覆盖：

- 默认值验证
- 边界情况（0 值、空字符串）
- 错误场景（无效输入）

### 测试标注格式

每个属性测试必须包含注释：

```python
# **Feature: state-config-tests, Property 1: Flat config priority over nested**
# **Validates: Requirements 1.1, 1.3, 2.1-2.4**
```

## 测试用例清单

### StrategyConfig 平铺/嵌套兼容性

| 用例 ID | 描述          | 输入                                             | 预期输出             |
| :------ | :------------ | :----------------------------------------------- | :------------------- |
| TC-1.1  | 仅平铺配置    | `chunking_mode="semantic", chunk_size=256`       | effective 返回平铺值 |
| TC-1.2  | 仅嵌套配置    | `chunking=ChunkingStrategy(mode="layout_aware")` | effective 返回嵌套值 |
| TC-1.3  | 平铺+嵌套混合 | 两者都设置                                       | effective 返回平铺值 |
| TC-1.4  | 都不设置      | 默认 StrategyConfig()                            | effective 返回默认值 |

### Effective 属性边界情况

| 用例 ID | 描述                  | 输入                    | 预期输出                                 |
| :------ | :-------------------- | :---------------------- | :--------------------------------------- |
| TC-2.1  | chunk_overlap=0       | `chunk_overlap=0`       | `chunk_overlap_effective == 0`           |
| TC-2.2  | preserve_tables=False | `preserve_tables=False` | `preserve_tables_effective == False`     |
| TC-2.3  | chunk_size=0          | `chunk_size=0`          | `chunk_size_effective == 0` (或验证错误) |

### channel_id 多租户验证

| 用例 ID | 描述                         | 输入                      | 预期输出                 |
| :------ | :--------------------------- | :------------------------ | :----------------------- |
| TC-3.1  | IngestState 缺 channel_id    | 不含 channel_id 的 dict   | 类型检查警告或运行时错误 |
| TC-3.2  | RetrievalState 缺 channel_id | 不含 channel_id 的 dict   | 类型检查警告或运行时错误 |
| TC-3.3  | search() 缺 channel_id       | `search(query, kb_names)` | TypeError                |
| TC-3.4  | 空字符串 channel_id          | `channel_id=""`           | ValueError 或拒绝        |

### 算法组件 channel_id 验证

| 用例 ID | 描述                           | 输入            | 预期输出   |
| :------ | :----------------------------- | :-------------- | :--------- |
| TC-4.1  | GraphLightState 缺 channel_id  | 不含 channel_id | KeyError   |
| TC-4.2  | RaptorLightState 缺 channel_id | 不含 channel_id | KeyError   |
| TC-4.3  | collect_texts 空 channel_id    | `channel_id=""` | ValueError |

### 验证错误测试

| 用例 ID | 描述               | 输入                      | 预期输出                |
| :------ | :----------------- | :------------------------ | :---------------------- |
| TC-5.1  | 无效 chunking_mode | `chunking_mode="invalid"` | ValidationError         |
| TC-5.2  | 负数 chunk_size    | `chunk_size=-100`         | 接受或 ValidationError  |
| TC-5.3  | 序列化往返         | 任意有效 config           | 往返后 effective 值不变 |
