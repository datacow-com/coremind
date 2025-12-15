# Requirements Document

## Introduction

Phase 2 垂直领域增强是 OmniRAG 系统的核心能力扩展，旨在为 core 模块接入垂直场景的深度解读和叙事能力。本阶段在 Phase 1 多云算力基础设施之上，构建统一的领域解读基座（`core/domains/`），支持命理分析、四联漫画等垂直场景的专业化处理。

核心价值：RAG 系统的真正价值在于"垂直化"处理能力——能够深度解读特定领域的内容，形成准确的结构化解读信息，而非简单的文本提取。

设计原则：

1. **不另起炉灶**：所有增强在现有 core 文件内完成，共同能力放 `core/domains/`
2. **真实数据优先**：每阶段使用真实样本和真实云 API
3. **GPU 标注与降级**：明确 requires_gpu 和推荐显存，提供 CPU/云 API 降级路径
4. **成本前置**：在路由前调用 cost_estimator，超预算自动降级

## Glossary

- **DomainInterpreter**: 领域解读器，负责将原始文档转换为领域特定的结构化叙事
- **Ontology**: 本体定义，描述领域内的概念、关系和规则
- **NarrativeEngine**: 叙事引擎，将结构化数据转换为连贯的叙事文本
- **VisualSchema**: 视觉模式定义，描述领域内的视觉元素识别规则
- **InterpretationResult**: 解读结果，包含结构化数据和叙事文本
- **DomainRegistry**: 领域注册表，管理所有已注册的领域解读器
- **ComputeProvider**: 算力提供商（Phase 1 已实现），提供 LLM/VLM 调用能力

## Requirements

### Requirement 1

**User Story:** As a system architect, I want a unified domain interpretation framework, so that vertical domains can be added without modifying core infrastructure.

#### Acceptance Criteria

1. WHEN a new domain interpreter is registered THEN the DomainRegistry SHALL store the interpreter with its ontology and configuration
2. WHEN interpret_document is called with a document THEN the system SHALL route to the appropriate domain interpreter based on document type or explicit domain parameter
3. WHEN a domain interpreter processes a document THEN the system SHALL return an InterpretationResult containing structured data and narrative text
4. WHEN no domain interpreter matches THEN the system SHALL fall back to generic text extraction without error
5. WHEN a domain interpreter requires GPU THEN the system SHALL check availability and fall back to cloud API if unavailable

### Requirement 2

**User Story:** As a developer, I want a base domain interpreter class, so that I can implement new vertical domains with consistent interfaces.

#### Acceptance Criteria

1. WHEN BaseDomainInterpreter is subclassed THEN the subclass SHALL implement interpret(), get_ontology(), and validate_output() methods
2. WHEN interpret() is called THEN the interpreter SHALL return an InterpretationResult with domain-specific structured data
3. WHEN validate_output() is called with an InterpretationResult THEN the system SHALL verify the result conforms to the domain ontology
4. WHEN the interpreter needs VLM capabilities THEN the interpreter SHALL use the compute provider from Phase 1 infrastructure
5. WHEN interpretation fails THEN the interpreter SHALL raise DomainInterpretationError with detailed context

### Requirement 3

**User Story:** As a system architect, I want ontology schema support, so that domain knowledge can be formally defined and validated.

#### Acceptance Criteria

1. WHEN an ontology YAML is loaded THEN the system SHALL parse entity types, relationships, and validation rules
2. WHEN structured data is produced THEN the system SHALL validate it against the ontology schema
3. WHEN validation fails THEN the system SHALL report specific schema violations
4. WHEN ontology defines required fields THEN the system SHALL ensure all required fields are present in output
5. WHEN ontology defines enum values THEN the system SHALL validate field values against allowed enums

### Requirement 4

**User Story:** As a content creator, I want a narrative engine, so that structured interpretation results can be converted to readable text.

#### Acceptance Criteria

1. WHEN NarrativeEngine receives structured data THEN the engine SHALL generate coherent narrative text following domain templates
2. WHEN narrative templates are defined THEN the engine SHALL use domain-specific templates for text generation
3. WHEN LLM is available THEN the engine SHALL use LLM to enhance narrative quality
4. WHEN LLM is unavailable THEN the engine SHALL fall back to template-based generation
5. WHEN generating narrative THEN the engine SHALL respect the detail_level parameter (brief, detailed, comprehensive)

### Requirement 5

**User Story:** As a metaphysics analyst, I want to interpret fortune-telling documents, so that I can extract structured readings from traditional texts and images.

#### Acceptance Criteria

1. WHEN a metaphysics document is processed THEN the MetaphysicsInterpreter SHALL identify key elements (八字, 五行, 神煞, etc.)
2. WHEN an image contains metaphysics charts THEN the interpreter SHALL use VLM to extract visual elements
3. WHEN elements are extracted THEN the interpreter SHALL apply domain rules to generate interpretation
4. WHEN interpretation is complete THEN the system SHALL produce both structured data and narrative explanation
5. WHEN processing Chinese text THEN the interpreter SHALL correctly handle traditional and simplified characters

### Requirement 6

**User Story:** As a comic analyst, I want to interpret four-panel comics, so that I can extract narrative structure, art style, and story elements.

#### Acceptance Criteria

1. WHEN a comic image is processed THEN the ComicInterpreter SHALL detect panel boundaries using panel_detector
2. WHEN panels are detected THEN the interpreter SHALL extract dialogue from speech bubbles using OCR
3. WHEN panels are analyzed THEN the interpreter SHALL use VLM to describe scene content and character actions
4. WHEN all panels are processed THEN the interpreter SHALL construct a coherent story narrative
5. WHEN art style analysis is enabled THEN the interpreter SHALL identify visual style characteristics

### Requirement 7

**User Story:** As a system operator, I want GPU resource management, so that compute-intensive operations are cost-effective and don't become bottlenecks.

#### Acceptance Criteria

1. WHEN a domain interpreter requires GPU THEN the manifest SHALL declare requires_gpu and recommended_vram_mb
2. WHEN GPU is unavailable locally THEN the system SHALL automatically route to cloud VLM providers
3. WHEN cloud API is used THEN the system SHALL apply cost estimation before execution
4. WHEN cost exceeds threshold THEN the system SHALL either warn or block based on configuration
5. WHEN multiple providers are available THEN the system SHALL select based on routing_strategy from Phase 1

### Requirement 8

**User Story:** As a developer, I want integration with existing core modules, so that domain interpretation works seamlessly with ingestion and retrieval pipelines.

#### Acceptance Criteria

1. WHEN domain interpretation is enabled THEN the ingestion pipeline SHALL invoke domain interpreters after parsing
2. WHEN InterpretationResult is produced THEN the system SHALL store both structured data and narrative in the document store
3. WHEN retrieval is performed THEN the system SHALL include domain-specific metadata in search results
4. WHEN manifest.yaml defines a domain capability THEN the capability SHALL be loadable via the existing capability system
5. WHEN domain interpretation fails THEN the ingestion pipeline SHALL continue with standard processing
