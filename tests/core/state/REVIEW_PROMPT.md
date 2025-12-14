# tests/core/state 测试用例专业审查 Prompt

## Context

**代码仓**: OmniRAG  
**关注目录**: `tests/core/state/**`  
**被测代码**: `core/state.py`（StrategyConfig、ChunkingStrategy、AlgorithmConfig、IngestState、RetrievalState、TypedDict 定义等）  
**当前问题**: 需要系统性审查测试质量，识别覆盖缺口和潜在 bug，而非仅完成任务

---

## 目标

通过执行并审查 `tests/core/state/**` 的测试来**发现缺陷**，确保：
1. **配置兼容性正确性**：平铺/嵌套配置优先级、默认值、边界值处理
2. **多租户隔离安全性**：channel_id 必填验证、类型安全
3. **状态结构完整性**：TypedDict 字段完整性、类型约束
4. **向后兼容性**：配置迁移路径、字段废弃处理

---

## 关键特性与风险点（需重点检查）

### StrategyConfig 配置兼容性
- **平铺 vs 嵌套优先级**：`chunking_mode` vs `chunking.mode`，`chunk_size` vs `chunking.chunk_size` 等
- **Effective 属性逻辑**：`chunking_mode_effective`、`chunk_size_effective`、`chunk_overlap_effective`、`preserve_tables_effective`
- **边界值处理**：`chunk_overlap=0`、`preserve_tables=False` 等 falsy 值不应被当作 None
- **默认值行为**：仅嵌套配置时使用嵌套默认值；仅平铺配置时使用平铺值
- **验证错误**：无效 `chunking_mode`、负数 `chunk_size`、`chunk_overlap > chunk_size` 等

### 多租户隔离（Channel ID）
- **IngestState channel_id**：TypedDict 必填字段验证（静态类型检查）
- **RetrievalState channel_id**：必填字段验证
- **运行时验证**：TypedDict 不强制运行时检查，但业务逻辑应验证
- **空值处理**：空字符串 `""` vs `None` vs 缺失字段的处理差异

### 状态结构完整性
- **TypedDict 字段完整性**：IngestState、RetrievalState、ProcessedChunk、ChunkMetadata 等
- **类型约束**：Literal 类型（如 `block_type`）、Optional 字段、默认值
- **嵌套结构**：`strategy_config` 字典结构、`metadata` 嵌套字典

### 配置字段覆盖
- **OCR/VLM 策略**：`ocr_provider`、`ocr_fallback_chain`、`force_ocr`、`detect_complex_layout`
- **分块策略**：`chunking`（嵌套）、`chunking_mode`/`chunk_size`/`chunk_overlap`/`preserve_tables`（平铺）
- **Embedding 策略**：`embedding_model`、`embedding_batch_size`、`embedding_dimensions`
- **索引策略**：`vector_backend`、`keyword_backend`、`enable_quantization`、`enable_multimodal_index`
- **算法配置**：`algorithms.enable_raptor`、`algorithms.enable_graphrag` 等
- **质量控制**：`enable_cleaning`、`min_quality_score`、`enable_dedup`、`enable_pii_filter`
- **缓存与检测**：`enable_semantic_cache`、`cache_ttl`、`enable_hallucination_check`、`hallucination_threshold`

---

## 动作指示

### 1) 测试用例用法与价值说明

**列出主要测试文件及其覆盖的功能点：**

- `test_strategy_config.py`：
  - 平铺配置优先级（Property 1）
  - 嵌套配置回退（Property 2）
  - 无效配置验证（Property 5）
  - **价值**：确保前端/API 传递的平铺配置能正确覆盖嵌套默认值，避免配置错位导致功能异常

- `test_effective_properties.py`：
  - Falsy 值处理（Property 3）：`chunk_overlap=0`、`preserve_tables=False` 不应被当作未设置
  - **价值**：防止显式设置的 falsy 值被误判为 None，导致使用错误的默认值

- `test_channel_id_validation.py`：
  - IngestState/RetrievalState channel_id 必填验证
  - MultimodalRetriever.search() channel_id 强制要求
  - GraphLightState/RaptorLightState channel_id 要求
  - **价值**：确保多租户隔离，防止跨租户数据泄露（P0 安全风险）

**说明每类测试能捕获的缺陷类型：**
- 配置优先级错误 → 功能行为不符合预期
- Falsy 值误判 → 显式设置被忽略
- channel_id 缺失 → 多租户数据泄露（P0）
- 类型约束失效 → 运行时错误或数据污染

---

### 2) 执行与结果收集

**执行命令：**
```bash
# 基础执行
pytest tests/core/state -v

# 带覆盖率
pytest tests/core/state --cov=core.state --cov-report=term-missing

# 特定测试文件
pytest tests/core/state/test_strategy_config.py -v
pytest tests/core/state/test_effective_properties.py -v
pytest tests/core/state/test_channel_id_validation.py -v

# Hypothesis 测试（生成更多随机用例）
pytest tests/core/state -v --hypothesis-show-statistics
```

**环境要求：**
- Python 3.11+
- pytest、hypothesis、pydantic
- 无需外部服务（纯单元测试）

**观察重点：**
- Hypothesis 生成的随机用例是否发现边界问题
- 覆盖率报告中的未覆盖行（特别是 `*_effective` 属性）
- 类型检查警告（mypy/pyright）

---

### 3) 覆盖率与缺口评估

**已覆盖的关键路径：**
- ✅ 平铺配置优先级（Property 1）
- ✅ 嵌套配置回退（Property 2）
- ✅ Falsy 值处理（Property 3）
- ✅ 无效配置验证（Property 5）
- ✅ channel_id 类型注解验证（静态检查）

**缺失或薄弱的场景（按优先级）：**

**P0（崩溃/安全/不可用）：**
- ❌ **运行时 channel_id 验证缺失**：TypedDict 不强制运行时检查，业务逻辑应验证但可能未覆盖
- ❌ **空字符串 channel_id 处理**：`channel_id=""` 是否被接受？应拒绝但可能未测试
- ❌ **配置字段类型错误**：传入非预期类型（如 `chunk_size="512"` 字符串）的验证

**P1（质量/设计对齐）：**
- ❌ **部分配置字段未测试**：`ocr_fallback_chain`、`embedding_dimensions`、`algorithms.*` 等
- ❌ **默认值边界**：`chunk_size=0`、`chunk_overlap<0`、`chunk_overlap>chunk_size` 的验证
- ❌ **嵌套配置部分字段覆盖**：仅设置 `chunking.mode` 但 `chunk_size` 使用默认值的情况
- ❌ **TypedDict 字段缺失运行时行为**：IngestState/RetrievalState 缺少必填字段时的实际行为

**P2（增强/观测）：**
- ❌ **配置序列化/反序列化**：JSON 序列化后反序列化是否保持一致性
- ❌ **配置合并**：多个配置对象合并时的优先级
- ❌ **废弃字段处理**：未来废弃字段的兼容性

---

### 4) 缺陷探测导向的优化目标

**优先补测/加深的高风险场景：**

1. **运行时 channel_id 验证（P0）**
   - **用例名**：`test_runtime_channel_id_validation_in_ingest`
   - **目的**：验证业务逻辑（如 loader/router）在运行时检查 channel_id 存在性
   - **步骤**：创建缺少 channel_id 的 IngestState，调用实际业务函数，断言抛出 ValueError 或记录错误
   - **关键断言**：错误日志包含 "channel_id is required" 或抛出异常

2. **空字符串 channel_id 拒绝（P0）**
   - **用例名**：`test_empty_string_channel_id_rejected`
   - **目的**：确保 `channel_id=""` 被拒绝，防止多租户隔离失效
   - **步骤**：创建 `channel_id=""` 的 IngestState/RetrievalState，调用验证函数
   - **关键断言**：抛出 ValueError 或返回错误状态

3. **配置字段类型错误验证（P0）**
   - **用例名**：`test_invalid_type_chunk_size_rejected`
   - **目的**：确保 `chunk_size="512"`（字符串）被 Pydantic 拒绝
   - **步骤**：尝试创建 `StrategyConfig(chunk_size="512")`
   - **关键断言**：抛出 ValidationError

4. **chunk_overlap > chunk_size 验证（P1）**
   - **用例名**：`test_chunk_overlap_exceeds_chunk_size_rejected`
   - **目的**：防止逻辑错误（overlap 不应大于 size）
   - **步骤**：创建 `StrategyConfig(chunk_size=100, chunk_overlap=200)`
   - **关键断言**：抛出 ValidationError 或警告

5. **部分嵌套配置覆盖（P1）**
   - **用例名**：`test_partial_nested_config_fallback`
   - **目的**：仅设置 `chunking.mode` 时，其他字段使用默认值
   - **步骤**：创建 `StrategyConfig(chunking=ChunkingStrategy(mode="semantic"))`，验证 `chunk_size_effective` 使用默认值 512
   - **关键断言**：`chunk_size_effective == 512`

6. **配置序列化一致性（P2）**
   - **用例名**：`test_config_serialization_roundtrip`
   - **目的**：JSON 序列化/反序列化后配置保持一致
   - **步骤**：创建 StrategyConfig → JSON → 反序列化 → 比较 effective 属性
   - **关键断言**：所有 effective 属性值一致

---

### 5) 发现问题时的输出格式

**对于每个发现的缺陷/缺口，输出：**

```
【缺陷/缺口 ID】: STATE-TEST-001
【用例/场景名称】: 运行时 channel_id 验证缺失
【严重级别】: P0（安全风险）
【复现步骤】:
1. 创建缺少 channel_id 的 IngestState（通过 dict 直接构造，绕过类型检查）
2. 调用 core.ingestion.nodes.loader.LoaderNode.__call__(state)
3. 观察是否抛出异常或记录错误

【期望行为】:
- 业务逻辑应检查 channel_id 存在性
- 缺失时抛出 ValueError 或记录 error_log

【实际行为】:
- [待执行测试后填写]

【推测根因】:
- TypedDict 不强制运行时检查
- 业务逻辑可能未添加显式验证

【建议修复点】:
- core/ingestion/nodes/loader.py: LoaderNode.__call__ 开头添加 channel_id 检查
- core/retrieval/nodes/retriever.py: HybridRetriever.__call__ 开头添加检查
- 或创建统一的 state 验证函数
```

---

## 输出期望

**结构化输出：**

1. **测试用例用法与价值**（1-2 页）
   - 各测试文件覆盖的功能点
   - 每类测试能捕获的缺陷类型
   - 测试的价值说明

2. **覆盖率评估**（1 页）
   - 已覆盖路径列表
   - 缺失场景列表（按 P0/P1/P2 分类）

3. **优先补测清单**（1-2 页）
   - 3-5 个高风险场景的用例骨架
   - 每个用例包含：名称、目的、步骤、关键断言

4. **执行结果**（如已执行）
   - 测试通过/失败统计
   - 发现的缺陷列表（按上述格式）
   - 覆盖率报告摘要

5. **优化建议**（1 页）
   - 测试结构改进建议
   - 缺失的测试类型建议
   - 工具/框架建议（如需要）

---

## 重点强调

**目标：发现 bug，而非完成任务**

- ✅ 关注**边界值**：0、负数、超大值、空字符串、None
- ✅ 关注**类型安全**：字符串传入数字字段、None 传入必填字段
- ✅ 关注**运行时行为**：TypedDict 不强制运行时检查，业务逻辑应补充验证
- ✅ 关注**配置兼容性**：平铺/嵌套混用、部分字段覆盖、序列化一致性
- ✅ 关注**多租户安全**：channel_id 缺失/空值可能导致数据泄露（P0）

**避免：**
- ❌ 仅验证"能运行"而不验证"行为正确"
- ❌ 忽略 Hypothesis 生成的边界用例
- ❌ 假设 TypedDict 提供运行时保护（实际不提供）

---

_生成时间: 2025-12-12_  
_适用版本: OmniRAG core/state.py v2.0+_

