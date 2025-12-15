# Implementation Plan

- [x] 1. 领域基座框架实现

  - [x] 1.1 创建 core/domains/ 目录结构

    - 创建 `core/domains/__init__.py`
    - 创建 `core/domains/registry.py`
    - 创建 `core/domains/base_interpreter.py`
    - 创建 `core/domains/ontology_schema.py`
    - 创建 `core/domains/narrative_engine.py`
    - 创建 `core/domains/exceptions.py`
    - _Requirements: 1.1, 2.1_

  - [x] 1.2 实现 DomainRegistry

    - 实现 register() 方法
    - 实现 get_interpreter() 方法
    - 实现 detect_domain() 方法
    - 实现 list_domains() 方法
    - _Requirements: 1.1, 1.2_

  - [x] 1.3 Write property test for domain registration round trip

    - **Property 1: Domain Registration Round Trip**
    - **Validates: Requirements 1.1, 1.2**

  - [x] 1.4 实现 BaseDomainInterpreter

    - 定义抽象方法 interpret(), get_ontology(), validate_output()
    - 实现 \_call_vlm() 使用 Phase 1 Gateway
    - 实现 \_call_llm() 使用 Phase 1 Gateway
    - 实现 GPU 可用性检查和云端回退
    - _Requirements: 2.1, 2.2, 2.4, 7.1_

  - [x] 1.5 Write property test for interpretation result completeness

    - **Property 2: Interpretation Result Completeness**
    - **Validates: Requirements 1.3, 2.2, 5.4**

  - [x] 1.6 Write unit tests for DomainRegistry and BaseDomainInterpreter
    - 测试注册和获取解读器
    - 测试领域检测
    - 测试 VLM/LLM 调用集成
    - _Requirements: 1.1, 1.2, 2.1_

- [x] 2. Checkpoint - 确保基座框架测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. 本体定义系统实现

  - [x] 3.1 实现 OntologySchema

    - 实现 from_yaml() 类方法
    - 实现 validate() 方法
    - 实现 EntityType 和 Relationship 数据类
    - 实现 FieldSpec 验证逻辑
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Write property test for ontology validation correctness

    - **Property 3: Ontology Validation Correctness**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**

  - [x] 3.3 Write unit tests for OntologySchema
    - 测试 YAML 解析
    - 测试必填字段验证
    - 测试枚举值验证
    - 测试类型验证
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. 叙事引擎实现

  - [x] 4.1 实现 NarrativeEngine

    - 实现 generate() 方法
    - 实现 register_template() 方法
    - 实现 \_template_fallback() 方法
    - 支持 detail_level 参数
    - _Requirements: 4.1, 4.2, 4.5_

  - [x] 4.2 Write property test for narrative generation respects detail level

    - **Property 4: Narrative Generation Respects Detail Level**
    - **Validates: Requirements 4.1, 4.5**

  - [x] 4.3 Write unit tests for NarrativeEngine
    - 测试 LLM 增强生成
    - 测试模板回退
    - 测试不同 detail_level
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 5. Checkpoint - 确保本体和叙事引擎测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. GPU 资源管理和成本集成

  - [x] 6.1 实现 GPU 可用性检查

    - 在 BaseDomainInterpreter 中实现 \_check_gpu_available()
    - 实现云端 VLM 自动回退
    - _Requirements: 7.1, 7.2_

  - [x] 6.2 Write property test for GPU fallback to cloud provider

    - **Property 5: GPU Fallback to Cloud Provider**
    - **Validates: Requirements 1.5, 7.2**

  - [x] 6.3 集成 Phase 1 成本追踪

    - 在 \_call_vlm() 和 \_call_llm() 中集成 CostTracker
    - 在调用前检查预算
    - _Requirements: 7.3, 7.4_

  - [x] 6.4 Write property test for cost estimation before execution

    - **Property 6: Cost Estimation Before Execution**
    - **Validates: Requirements 7.3, 7.4, 7.5**

  - [x] 6.5 Write unit tests for GPU management and cost integration
    - 测试 GPU 检查逻辑
    - 测试云端回退
    - 测试成本追踪集成
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 7. Checkpoint - 确保 GPU 和成本集成测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. 命理领域实现

  - [x] 8.1 创建命理领域目录结构

    - 创建 `core/domains/metaphysics/__init__.py`
    - 创建 `core/domains/metaphysics/interpreter.py`
    - 创建 `core/domains/metaphysics/ontology.yaml`
    - 创建 `core/domains/metaphysics/knowledge/` 目录
    - _Requirements: 5.1_

  - [x] 8.2 实现 MetaphysicsInterpreter

    - 实现 interpret() 方法
    - 实现文本元素提取（八字、五行、神煞）
    - 实现 VLM 图像解析
    - 实现命理规则应用
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 8.3 创建命理本体定义

    - 定义八字实体类型
    - 定义五行实体类型
    - 定义神煞实体类型
    - 定义关系和验证规则
    - _Requirements: 5.1, 3.1_

  - [x] 8.4 准备命理测试样本

    - 准备 10+ 条真实样例
    - 包含 PDF 和图像格式
    - 创建样本清单文档
    - _Requirements: 5.1, 5.2_

  - [x] 8.5 Write unit tests for MetaphysicsInterpreter
    - 测试元素提取
    - 测试 VLM 集成
    - 测试规则应用
    - 测试中文字符处理
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. 漫画领域实现

  - [x] 9.1 创建漫画领域目录结构

    - 创建 `core/domains/comic/__init__.py`
    - 创建 `core/domains/comic/interpreter.py`
    - 创建 `core/domains/comic/panel_detector.py`
    - 创建 `core/domains/comic/ontology.yaml`
    - _Requirements: 6.1_

  - [x] 9.2 实现 PanelDetector

    - 实现分格边界检测
    - 实现对话气泡检测
    - 支持从右到左和从左到右阅读顺序
    - _Requirements: 6.1_

  - [x] 9.3 实现 ComicInterpreter

    - 实现 interpret() 方法
    - 集成 PanelDetector
    - 实现 OCR 对话提取
    - 实现 VLM 场景描述
    - 实现故事叙事构建
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 9.4 创建漫画本体定义

    - 定义分格实体类型
    - 定义角色实体类型
    - 定义对话实体类型
    - 定义场景实体类型
    - _Requirements: 6.1, 3.1_

  - [x] 9.5 准备漫画测试样本

    - 准备 20+ 张真实样例
    - 包含四格漫画
    - 创建样本清单文档
    - _Requirements: 6.1, 6.5_

  - [x] 9.6 Write unit tests for ComicInterpreter
    - 测试分格检测
    - 测试 OCR 提取
    - 测试 VLM 场景描述
    - 测试叙事构建
    - 测试艺术风格分析
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 10. Checkpoint - 确保领域实现测试通过

  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. 管道集成

  - [x] 11.1 创建 DomainRouter 节点

    - 在 `core/ingestion/nodes/domain_router.py` 创建路由节点
    - 实现领域检测和路由逻辑
    - 实现回退到标准处理
    - _Requirements: 1.2, 1.4, 8.1_

  - [x] 11.2 Write property test for pipeline integration resilience

    - **Property 7: Pipeline Integration Resilience**
    - **Validates: Requirements 8.5**

  - [x] 11.3 集成到 Ingestion Pipeline

    - 在 parser 之后添加 domain_router 节点
    - 存储 InterpretationResult 到文档存储
    - _Requirements: 8.1, 8.2_

  - [x] 11.4 更新 manifest.yaml

    - 添加 vertical_domain 能力卡
    - 添加 metaphysics_interpretation 能力
    - 添加 comic_interpretation 能力
    - 标注 requires_gpu 和推荐显存
    - _Requirements: 7.1, 8.4_

  - [x] 11.5 Write unit tests for pipeline integration
    - 测试领域路由
    - 测试结果存储
    - 测试失败回退
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [x] 12. 集成测试

  - [x] 12.1 创建真实 API 测试

    - 创建 `tests/integration/test_domain_real_api.py`
    - 测试命理解读真实 API 调用
    - 测试漫画解读真实 API 调用
    - _Requirements: 5.1, 6.1_

  - [x] 12.2 创建端到端测试
    - 创建 `tests/integration/test_phase2_e2e.py`
    - 测试完整的领域解读流程
    - 测试成本追踪集成
    - 测试 GPU 回退
    - _Requirements: 8.1, 8.2, 8.3_

- [x] 13. 回归测试

  - [x] 13.1 运行现有测试
    - 运行 `pytest tests/core/ -v`
    - 确保所有现有测试通过
    - 确保 Phase 1 测试仍然通过
    - _Requirements: 8.5_

- [ ] 14. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
