# Implementation Plan

- [x] 1. 设置测试基础设施

  - [x] 1.1 创建测试目录和 conftest.py
    - 创建 `tests/core/state/` 目录
    - 创建 `conftest.py` 包含共享 fixtures 和 hypothesis strategies
    - 定义 `chunking_strategy`, `flat_config`, `channel_id` 生成器
    - _Requirements: 5.4_
  - [x] 1.2 验证 hypothesis 依赖
    - 确认 `requirements-dev.txt` 包含 `hypothesis>=6.0.0`
    - _Requirements: 5.4_

- [x] 2. StrategyConfig 平铺/嵌套兼容性测试

  - [x] 2.1 实现 Property 1: 平铺配置优先于嵌套
    - 创建 `tests/core/state/test_strategy_config.py`
    - 使用 hypothesis 生成随机平铺和嵌套配置
    - 验证当两者都存在时，effective 属性返回平铺值
    - **Property 1: Flat config priority over nested**
    - **Validates: Requirements 1.1, 1.3, 2.1-2.4**
    - _Requirements: 1.1, 1.3_
  - [x] 2.2 实现 Property 2: 嵌套回退测试
    - 验证当平铺字段为 None 时，effective 返回嵌套值
    - **Property 2: Nested fallback when flat is None**
    - **Validates: Requirements 1.2, 2.1-2.4**
    - _Requirements: 1.2_
  - [x] 2.3 实现默认值测试 (TC-1.4)
    - 测试默认 StrategyConfig() 返回 ChunkingStrategy 默认值
    - _Requirements: 1.4_

- [-] 3. Effective 属性边界情况测试

  - [x] 3.1 实现 Property 3: Falsy 值测试
    - 创建 `tests/core/state/test_effective_properties.py`
    - 测试 chunk_overlap=0 时 effective 返回 0
    - 测试 preserve_tables=False 时 effective 返回 False
    - **Property 3: Falsy values are not treated as unset**
    - **Validates: Requirements 2.5**
    - _Requirements: 2.5_
  - [x] 3.2 实现 Property 4: 序列化往返测试
    - 测试 model_dump() 后重建保持 effective 值
    - **Property 4: Serialization round-trip preserves effective values**
    - **Validates: Requirements 5.4**
    - _Requirements: 5.4_

- [x] 4. Checkpoint - 确保配置测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. channel_id 多租户验证测试

  - [x] 5.1 创建 channel_id 验证测试文件
    - 创建 `tests/core/state/test_channel_id_validation.py`
    - _Requirements: 3.1, 3.2_
  - [x] 5.2 实现 IngestState channel_id 测试 (TC-3.1)
    - 测试创建不含 channel_id 的 IngestState 行为
    - 验证类型检查或运行时行为
    - _Requirements: 3.1_
  - [x] 5.3 实现 RetrievalState channel_id 测试 (TC-3.2)
    - 测试创建不含 channel_id 的 RetrievalState 行为
    - _Requirements: 3.2_
  - [x] 5.4 实现 MultimodalRetriever.search() channel_id 测试 (TC-3.3)
    - 测试调用 search() 不传 channel_id 抛出 TypeError
    - _Requirements: 3.4_
  - [x] 5.5 实现空字符串 channel_id 测试 (TC-3.4)
    - 测试 channel_id="" 时组件行为
    - _Requirements: 3.3_

- [x] 6. 算法组件 channel_id 测试

  - [x] 6.1 实现 GraphLightState channel_id 测试 (TC-4.1)
    - 测试 GraphLightState 缺少 channel_id 时的错误
    - _Requirements: 4.1_
  - [x] 6.2 实现 RaptorLightState channel_id 测试 (TC-4.2)
    - 测试 RaptorLightState 缺少 channel_id 时的错误
    - _Requirements: 4.2_
  - [x] 6.3 实现 collect_texts 空 channel_id 测试 (TC-4.3)
    - 测试 collect_texts 传入空字符串 channel_id 的行为
    - _Requirements: 4.3_

- [-] 7. 验证错误测试

  - [x] 7.1 实现 Property 5: 无效 chunking_mode 测试
    - 测试无效 chunking_mode 值抛出 ValidationError
    - **Property 5: Invalid chunking_mode raises validation error**
    - **Validates: Requirements 5.1**
    - _Requirements: 5.1_
  - [ ]\* 7.2 实现负数 chunk_size 测试 (TC-5.2)
    - 测试负数 chunk_size 的行为
    - _Requirements: 5.2_

- [x] 8. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
