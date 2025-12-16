# Implementation Plan

## Phase 1: Server API 补全

- [x] 1. KB Config API 实现

  - [x] 1.1 创建 `server/api/kb_config.py` 模块
    - 实现 GET `/api/kb/{kb_name}/capabilities` 端点
    - 实现 PUT `/api/kb/{kb_name}/capabilities` 端点
    - 实现 GET `/api/kb/{kb_name}/strategy` 端点
    - 定义 Pydantic 请求/响应模型
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 1.2 编写 KB Config API 属性测试
    - **Property 1: KB Capability Configuration Round-Trip**
    - **Validates: Requirements 1.2, 12.1**
  - [x] 1.3 实现配置验证逻辑
    - 基于 config_schema 验证配置
    - 返回详细验证错误信息
    - _Requirements: 1.4_
  - [x] 1.4 实现配置变更事件发射
    - 定义配置变更事件模型
    - 在配置更新时发射事件
    - _Requirements: 1.5_

- [x] 2. Algorithms API 实现

  - [x] 2.1 创建 `server/api/algorithms.py` 模块
    - 实现 POST `/api/algorithms/raptor/run` 端点
    - 实现 POST `/api/algorithms/graphrag/run` 端点
    - 实现 POST `/api/algorithms/mindmap/run` 端点
    - 实现 GET `/api/algorithms/{task_id}/status` 端点
    - 定义 Pydantic 请求/响应模型
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 2.2 编写算法任务创建属性测试
    - **Property 2: Algorithm Task Creation**
    - **Validates: Requirements 2.1, 2.2, 2.3**
  - [x] 2.3 实现 SSE 进度推送
    - 实现 GET `/api/algorithms/{task_id}/progress` SSE 端点
    - 定义进度事件格式 (stage, progress, message)
    - 实现连接中断重连支持
    - _Requirements: 2.4, 11.1, 11.2, 11.5_
  - [x] 2.4 编写 SSE 进度事件属性测试
    - **Property 3: SSE Progress Event Structure**
    - **Validates: Requirements 2.4, 11.2**
  - [x] 2.5 实现算法任务队列
    - 创建后台任务执行器
    - 实现任务状态持久化
    - 实现结果存储和 KB 元数据更新
    - _Requirements: 2.5, 2.6_
  - [x] 2.6 实现执行历史 API
    - 实现 GET `/api/algorithms/history` 端点
    - 支持按 KB、算法类型过滤
    - _Requirements: 8.6_
  - [x] 2.7 编写运行历史完整性属性测试
    - **Property 13: Run History Completeness**
    - **Validates: Requirements 8.6**

- [x] 3. Checkpoint - 确保所有测试通过

  - 确保所有测试通过，如有问题请询问用户

- [x] 4. Domains API 实现

  - [x] 4.1 创建 `server/api/domains.py` 模块
    - 实现 GET `/api/domains` 端点
    - 实现 GET `/api/domains/{domain_id}` 端点
    - 实现 GET `/api/domains/{domain_id}/ontology` 端点
    - 定义 Pydantic 请求/响应模型
    - _Requirements: 3.1, 3.2_
  - [x] 4.2 实现 KB 领域绑定 API
    - 实现 POST `/api/kb/{kb_name}/domain` 端点
    - 实现 GET `/api/kb/{kb_name}/domain` 端点
    - 实现依赖检查逻辑
    - _Requirements: 3.3, 3.4, 3.5_
  - [x] 4.3 编写领域绑定属性测试
    - **Property 4: Domain Binding Round-Trip**
    - **Validates: Requirements 3.3, 3.4**
  - [x] 4.4 编写本体结构有效性属性测试
    - **Property 14: Ontology Structure Validity**
    - **Validates: Requirements 9.5**

- [x] 5. LLM Gateway API 实现

  - [x] 5.1 创建 `server/api/llm_gateway.py` 模块
    - 实现 GET `/api/llm/routing-strategies` 端点
    - 实现 GET `/api/llm/providers` 端点
    - 定义 Pydantic 请求/响应模型
    - _Requirements: 4.1_
  - [x] 5.2 实现 KB LLM 配置 API
    - 实现 PUT `/api/kb/{kb_name}/llm-config` 端点
    - 实现 GET `/api/kb/{kb_name}/llm-config` 端点
    - 实现配置即时生效逻辑
    - _Requirements: 4.2, 4.3, 4.4_
  - [x] 5.3 编写 LLM 配置属性测试
    - **Property 5: LLM Config Round-Trip**
    - **Validates: Requirements 4.2, 4.3**

- [x] 6. 配置持久化实现

  - [x] 6.1 实现配置存储层
    - 创建配置存储接口
    - 实现数据库持久化
    - 实现配置加载逻辑
    - _Requirements: 12.1, 12.2_
  - [x] 6.2 实现配置版本历史
    - 创建版本历史表
    - 在配置更新时记录历史
    - _Requirements: 12.3_
  - [x] 6.3 编写配置版本历史属性测试
    - **Property 15: Configuration Version History**
    - **Validates: Requirements 12.3**
  - [x] 6.4 实现配置导出功能
    - 实现配置序列化
    - 包含所有能力设置
    - _Requirements: 12.4, 12.5_
  - [x] 6.5 编写配置序列化属性测试
    - **Property 10: Configuration Serialization Round-Trip**
    - **Validates: Requirements 13.1, 13.2**

- [x] 7. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户

## Phase 2: Frontend 能力市场与 KB 配置

- [x] 8. 前端状态管理

  - [x] 8.1 创建 `capabilityStore.ts`
    - 定义 CapabilityStore 接口
    - 实现能力列表获取
    - 实现 KB 配置管理
    - 实现算法任务管理
    - _Requirements: 5.1, 6.1_

- [x] 9. 动态配置表单组件

  - [x] 9.1 创建 `DynamicConfigForm.tsx`
    - 实现表单容器组件
    - 实现字段渲染逻辑
    - 实现验证错误显示
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  - [x] 9.2 实现各类型字段组件
    - 实现 SelectField 组件
    - 实现 SliderField 组件
    - 实现 SwitchField 组件
    - 实现 MultiSelectField 组件
    - 实现 NumberField 组件
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 9.3 实现条件字段显示逻辑
    - 解析 ui_show_if 条件
    - 实现字段可见性控制
    - _Requirements: 7.5_
  - [x] 9.4 编写动态表单组件属性测试
    - **Property 6: Dynamic Form Component Mapping**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
  - [x] 9.5 编写条件字段可见性属性测试
    - **Property 7: Conditional Field Visibility**
    - **Validates: Requirements 7.5**

- [x] 10. 能力市场页面

  - [x] 10.1 创建 `CapabilityStorePage.tsx`
    - 实现页面布局
    - 实现分类标签切换
    - 实现能力卡片网格
    - _Requirements: 5.1, 5.2_
  - [x] 10.2 实现 CapabilityCard 组件
    - 显示能力名称、图标、描述
    - 显示使用场景和配置状态
    - 实现配置按钮
    - _Requirements: 5.3, 5.4_
  - [x] 10.3 实现搜索功能
    - 实现搜索栏组件
    - 实现搜索过滤逻辑
    - _Requirements: 5.5_
  - [x] 10.4 编写能力搜索过滤属性测试
    - **Property 8: Capability Search Filtering**
    - **Validates: Requirements 5.5**
  - [x] 10.5 实现配置弹窗
    - 集成 DynamicConfigForm
    - 实现配置保存逻辑
    - _Requirements: 5.4_

- [x] 11. KB 能力配置页面

  - [x] 11.1 创建 `KBCapabilityConfig.tsx`
    - 实现已启用能力列表
    - 实现添加能力按钮
    - _Requirements: 6.1, 6.2_
  - [x] 11.2 实现能力启用/禁用功能
    - 实现添加能力弹窗
    - 实现能力启用逻辑
    - 实现能力禁用确认
    - _Requirements: 6.3, 6.6_
  - [x] 11.3 实现依赖状态显示
    - 检查能力依赖
    - 显示依赖状态
    - 阻止启用未满足依赖的能力
    - _Requirements: 6.5_
  - [x] 11.4 编写依赖强制执行属性测试
    - **Property 9: Dependency Enforcement**
    - **Validates: Requirements 6.5, 3.5**
  - [x] 11.5 实现能力配置编辑
    - 集成 DynamicConfigForm
    - 实现配置验证和保存
    - _Requirements: 6.4_

- [x] 12. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户

## Phase 3: 算法控制台

- [x] 13. 算法控制台页面

  - [x] 13.1 创建 `AlgorithmConsolePage.tsx`
    - 实现页面布局
    - 实现算法配置面板
    - _Requirements: 8.1_
  - [x] 13.2 实现 RAPTOR 配置面板
    - KB 选择器
    - 模式选择 (Light/Deep)
    - 参数配置 (max_clusters, levels, summary_max_tokens)
    - _Requirements: 8.1, 8.2_
  - [x] 13.3 实现 GraphRAG 配置面板
    - KB 选择器
    - 实体类型选择
    - 社区检测配置
    - _Requirements: 8.1, 8.2_
  - [x] 13.4 实现 MindMap 配置面板
    - KB 选择器
    - 模式选择
    - 参数配置
    - _Requirements: 8.1, 8.2_
  - [x] 13.5 实现成本估算显示
    - 基于 KB 大小和配置计算估算成本
    - 实时更新显示
    - _Requirements: 8.2_
  - [ ]\* 13.6 编写成本估算一致性属性测试
    - **Property 12: Cost Estimation Consistency**
    - **Validates: Requirements 8.2**

- [x] 14. 算法执行与进度显示

  - [x] 14.1 实现算法执行功能
    - 调用算法 API
    - 建立 SSE 连接
    - _Requirements: 8.3_
  - [x] 14.2 实现进度条组件
    - 显示当前阶段
    - 显示进度百分比
    - 显示已用时间
    - _Requirements: 8.4_
  - [ ]\* 14.3 编写算法进度单调性属性测试
    - **Property 11: Algorithm Progress Monotonicity**
    - **Validates: Requirements 2.4, 8.4**
  - [x] 14.4 实现完成状态显示
    - 显示成功/失败状态
    - 显示结果摘要
    - _Requirements: 8.5_
  - [x] 14.5 实现运行历史表格
    - 显示历史执行记录
    - 显示状态、耗时、成本
    - _Requirements: 8.6_

- [x] 15. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户

## Phase 4: 领域管理与 LLM 策略

- [x] 16. 领域管理页面

  - [x] 16.1 创建 `DomainManagerPage.tsx`
    - 实现页面布局
    - 实现领域卡片列表
    - _Requirements: 9.1_
  - [x] 16.2 实现 DomainCard 组件
    - 显示领域名称、描述、图标
    - 显示支持格式和依赖
    - _Requirements: 9.1_
  - [x] 16.3 实现本体查看器
    - 显示实体列表
    - 显示关系列表
    - 显示属性定义
    - _Requirements: 9.2, 9.5_
  - [x] 16.4 实现领域绑定功能
    - KB 选择器
    - 领域选择
    - 配置表单
    - _Requirements: 9.3, 9.4_

- [x] 17. LLM 策略配置页面

  - [x] 17.1 创建 `LLMStrategyPage.tsx`
    - 实现页面布局
    - 实现策略选择器
    - _Requirements: 10.1, 10.2_
  - [x] 17.2 实现预算配置
    - 预算限额输入
    - 当前使用量显示
    - 输入验证
    - _Requirements: 10.3_
  - [x] 17.3 实现降级链编辑器
    - 模型列表显示
    - 拖拽排序功能
    - _Requirements: 10.4_
  - [x] 17.4 实现配置保存
    - 调用 API 保存配置
    - 显示保存确认
    - _Requirements: 10.5_

- [x] 18. 路由和导航集成

  - [x] 18.1 添加新页面路由
    - 添加算法控制台路由
    - 添加领域管理路由
    - 添加 LLM 策略路由
    - _Requirements: 8.1, 9.1, 10.1_
  - [x] 18.2 更新导航菜单
    - 添加新页面入口
    - 更新 KB 详情页 Tab
    - _Requirements: 8.1, 9.1, 10.1_

- [ ] 19. Final Checkpoint - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户
