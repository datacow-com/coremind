# Requirements Document

## Introduction

本需求文档定义了 OmniRAG 能力可视化系统的功能需求。该系统旨在将 core 中的核心能力（Ingestion Pipeline、Retrieval Pipeline、高级算法、LLM Gateway、垂直领域等）可视化，使其成为用户可以配置、操作、选择、使用的资产。

系统分为四个主要阶段：

1. **Phase 1**: Server API 补全 - 完善后端 API 接口
2. **Phase 2**: 能力市场与 KB 配置 - 前端能力展示与配置界面
3. **Phase 3**: 算法控制台 - 高级算法的可视化执行与监控
4. **Phase 4**: 领域管理与 LLM 策略 - 垂直领域和 LLM 路由配置

## Glossary

- **Capability (能力)**: 系统中可配置的功能模块，定义在 manifest.yaml 中
- **KB (Knowledge Base, 知识库)**: 用户创建的知识存储单元，可启用不同能力
- **manifest.yaml**: 能力清单配置文件，定义所有能力的元数据和配置 schema
- **config_schema**: 能力的配置模式定义，用于动态生成配置表单
- **RAPTOR**: 递归摘要聚类算法，构建多层知识树
- **GraphRAG**: 知识图谱算法，进行实体关系抽取和社区检测
- **MindMap**: 思维导图算法，生成文档结构化摘要
- **Domain (领域)**: 垂直领域解读器，如 Comic、Metaphysics
- **Ontology (本体)**: 领域知识的结构化定义
- **LLM Gateway**: LLM 路由网关，支持多策略路由和成本控制
- **SSE (Server-Sent Events)**: 服务器推送事件，用于实时进度更新
- **Channel**: 多租户隔离的顶层单元

## Requirements

### Requirement 1: KB 能力配置 API

**User Story:** As a developer, I want to configure capabilities for a knowledge base via API, so that I can enable/disable features and customize their settings programmatically.

#### Acceptance Criteria

1. WHEN a client sends GET request to `/api/kb/{kb_name}/capabilities` THEN the System SHALL return the list of enabled capabilities with their current configurations for that KB
2. WHEN a client sends PUT request to `/api/kb/{kb_name}/capabilities` with capability configurations THEN the System SHALL validate and persist the capability settings for that KB
3. WHEN a client sends GET request to `/api/kb/{kb_name}/strategy` THEN the System SHALL return the merged complete strategy configuration including all capability settings
4. IF a capability configuration fails validation THEN the System SHALL return a 400 response with specific validation error messages
5. WHEN capability configuration is updated THEN the System SHALL emit a configuration change event for downstream consumers

### Requirement 2: 算法执行 API

**User Story:** As a user, I want to execute advanced algorithms (RAPTOR, GraphRAG, MindMap) on my knowledge base via API, so that I can build enhanced knowledge structures.

#### Acceptance Criteria

1. WHEN a client sends POST request to `/api/algorithms/raptor/run` with KB name and configuration THEN the System SHALL start a RAPTOR algorithm task and return a task ID
2. WHEN a client sends POST request to `/api/algorithms/graphrag/run` with KB name and configuration THEN the System SHALL start a GraphRAG algorithm task and return a task ID
3. WHEN a client sends POST request to `/api/algorithms/mindmap/run` with KB name and configuration THEN the System SHALL start a MindMap algorithm task and return a task ID
4. WHEN a client connects to `/api/algorithms/{task_id}/progress` via SSE THEN the System SHALL stream real-time progress updates including stage, percentage, and status messages
5. WHEN an algorithm task completes THEN the System SHALL persist the results and update the KB metadata
6. IF an algorithm task fails THEN the System SHALL record the error details and notify via SSE with failure status

### Requirement 3: 领域管理 API

**User Story:** As a user, I want to manage vertical domains and their ontologies via API, so that I can configure domain-specific interpretation for my knowledge bases.

#### Acceptance Criteria

1. WHEN a client sends GET request to `/api/domains` THEN the System SHALL return the list of all registered domains with their metadata
2. WHEN a client sends GET request to `/api/domains/{domain_id}/ontology` THEN the System SHALL return the ontology schema for that domain
3. WHEN a client sends POST request to `/api/kb/{kb_name}/domain` with domain configuration THEN the System SHALL bind the specified domain to the KB
4. WHEN a client sends GET request to `/api/kb/{kb_name}/domain` THEN the System SHALL return the currently bound domain and its configuration
5. IF a domain binding fails due to missing dependencies THEN the System SHALL return a 400 response listing the missing requirements

### Requirement 4: LLM Gateway 配置 API

**User Story:** As a user, I want to configure LLM routing strategies and budget limits via API, so that I can optimize cost and performance for my knowledge base.

#### Acceptance Criteria

1. WHEN a client sends GET request to `/api/llm/routing-strategies` THEN the System SHALL return the list of available routing strategies with descriptions
2. WHEN a client sends PUT request to `/api/kb/{kb_name}/llm-config` with routing configuration THEN the System SHALL update the LLM routing settings for that KB
3. WHEN a client sends GET request to `/api/kb/{kb_name}/llm-config` THEN the System SHALL return the current LLM configuration including strategy, budget, and fallback chain
4. WHEN LLM configuration is updated THEN the System SHALL apply the new routing strategy immediately for subsequent requests
5. IF budget limit is exceeded THEN the System SHALL trigger the fallback chain according to configuration

### Requirement 5: 能力市场页面

**User Story:** As a user, I want to browse all available capabilities in a marketplace-style interface, so that I can discover and understand what features are available.

#### Acceptance Criteria

1. WHEN a user navigates to the Capability Store page THEN the System SHALL display all capabilities as cards grouped by category (Basic, Enhanced, Pro, Advanced)
2. WHEN a user clicks on a category tab THEN the System SHALL filter the displayed capabilities to show only that category
3. WHEN a user views a capability card THEN the System SHALL display the capability name, icon, description, use case, and configuration status
4. WHEN a user clicks the configure button on a capability card THEN the System SHALL open a configuration modal with a dynamically generated form based on config_schema
5. WHEN a user searches for capabilities THEN the System SHALL filter capabilities by name and description matching the search term

### Requirement 6: KB 能力配置页面

**User Story:** As a user, I want to configure capabilities for my knowledge base through a visual interface, so that I can easily enable features and customize their settings.

#### Acceptance Criteria

1. WHEN a user navigates to KB detail page and selects "Capability Config" tab THEN the System SHALL display the list of enabled capabilities with their current configurations
2. WHEN a user clicks "Add Capability" button THEN the System SHALL display a modal with available capabilities that can be enabled
3. WHEN a user enables a capability THEN the System SHALL add it to the KB configuration and display its configuration form
4. WHEN a user modifies capability configuration THEN the System SHALL validate the input and save the changes
5. WHEN a capability has dependencies THEN the System SHALL display dependency status and prevent enabling if dependencies are not met
6. WHEN a user disables a capability THEN the System SHALL remove it from the KB configuration after confirmation

### Requirement 7: 动态配置表单生成

**User Story:** As a developer, I want configuration forms to be automatically generated from config_schema, so that new capabilities can be added without frontend code changes.

#### Acceptance Criteria

1. WHEN config_schema specifies ui_component as "select" THEN the System SHALL render a dropdown select component with enum options
2. WHEN config_schema specifies ui_component as "slider" THEN the System SHALL render a slider component with min, max, and step values
3. WHEN config_schema specifies ui_component as "switch" THEN the System SHALL render a toggle switch for boolean values
4. WHEN config_schema specifies ui_component as "multi-select" THEN the System SHALL render a multi-select component for array values
5. WHEN config_schema specifies ui_show_if condition THEN the System SHALL conditionally show/hide the field based on another field's value
6. WHEN a form field has validation constraints THEN the System SHALL display validation errors inline

### Requirement 8: 算法控制台页面

**User Story:** As a user, I want to execute and monitor advanced algorithms through a visual console, so that I can build enhanced knowledge structures without using APIs directly.

#### Acceptance Criteria

1. WHEN a user navigates to Algorithm Console page THEN the System SHALL display configuration panels for RAPTOR, GraphRAG, and MindMap algorithms
2. WHEN a user selects a target KB and configures algorithm parameters THEN the System SHALL display estimated cost based on KB size and configuration
3. WHEN a user clicks "Run" button THEN the System SHALL start the algorithm and display a real-time progress bar
4. WHEN an algorithm is running THEN the System SHALL display current stage, percentage, and elapsed time
5. WHEN an algorithm completes THEN the System SHALL display success status with result summary
6. WHEN a user views run history THEN the System SHALL display past algorithm executions with status, duration, and cost

### Requirement 9: 领域管理页面

**User Story:** As a user, I want to manage vertical domains through a visual interface, so that I can configure domain-specific interpretation for my knowledge bases.

#### Acceptance Criteria

1. WHEN a user navigates to Domain Manager page THEN the System SHALL display all registered domains as cards with their metadata
2. WHEN a user clicks on a domain card THEN the System SHALL display the domain's ontology schema in a readable format
3. WHEN a user selects a KB and binds a domain THEN the System SHALL update the KB's domain configuration
4. WHEN a domain has specific configuration options THEN the System SHALL display a configuration form for those options
5. WHEN a user views a domain's ontology THEN the System SHALL display entities, attributes, and relations in a structured view

### Requirement 10: LLM 策略配置页面

**User Story:** As a user, I want to configure LLM routing strategies through a visual interface, so that I can optimize cost and performance for my knowledge base.

#### Acceptance Criteria

1. WHEN a user navigates to LLM Strategy page THEN the System SHALL display available routing strategies with descriptions
2. WHEN a user selects a routing strategy THEN the System SHALL display strategy-specific configuration options
3. WHEN a user configures budget limit THEN the System SHALL validate the input and display current usage
4. WHEN a user configures fallback chain THEN the System SHALL allow drag-and-drop ordering of fallback models
5. WHEN configuration is saved THEN the System SHALL apply changes immediately and display confirmation

### Requirement 11: SSE 进度推送

**User Story:** As a developer, I want real-time progress updates via SSE, so that the frontend can display live progress for long-running operations.

#### Acceptance Criteria

1. WHEN an algorithm task starts THEN the System SHALL establish an SSE connection and begin streaming progress events
2. WHEN progress updates occur THEN the System SHALL emit events with stage name, percentage (0-100), and status message
3. WHEN a task completes successfully THEN the System SHALL emit a completion event with result summary and close the connection
4. IF a task fails THEN the System SHALL emit a failure event with error details and close the connection
5. WHEN SSE connection is interrupted THEN the System SHALL support reconnection and resume from current state

### Requirement 12: 能力配置持久化

**User Story:** As a user, I want my capability configurations to be persisted, so that they are retained across sessions and system restarts.

#### Acceptance Criteria

1. WHEN capability configuration is saved THEN the System SHALL persist it to the database associated with the KB
2. WHEN a KB is loaded THEN the System SHALL restore all capability configurations from persistent storage
3. WHEN capability configuration is updated THEN the System SHALL maintain version history for audit purposes
4. WHEN a capability is disabled THEN the System SHALL retain its last configuration for potential re-enablement
5. WHEN exporting KB configuration THEN the System SHALL include all capability settings in the export

### Requirement 13: 能力配置序列化与反序列化

**User Story:** As a developer, I want capability configurations to be serializable, so that they can be exported, imported, and version controlled.

#### Acceptance Criteria

1. WHEN serializing capability configuration THEN the System SHALL produce valid JSON that conforms to config_schema
2. WHEN deserializing capability configuration THEN the System SHALL validate against config_schema and report errors
3. WHEN importing configuration THEN the System SHALL merge with existing configuration according to merge strategy
4. WHEN configuration format changes THEN the System SHALL migrate old configurations to new format automatically
5. WHEN printing configuration THEN the System SHALL produce human-readable output with comments
