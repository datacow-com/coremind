# OmniRAG 系统架构深度理解 Prompt

> **目标受众**: 资深系统架构师  
> **目标**: 深入、完整理解 OmniRAG 工程架构、实现细节、设计决策、测试覆盖与优化空间  
> **文档版本**: v1.0 (2025-12-12)

---

## Context

**项目**: OmniRAG - 面向 100TB 规模的生产级 RAG 系统  
**核心目录**: `core/` - 包含摄取、检索、多模态、算法、存储等核心模块  
**测试状态**: 单元测试基本完成，覆盖 `tests/core/**`  
**参考文档**: `docs/tech/system-design.md`, `docs/tech/implementation_plan.md`, `docs/tech/large-pdf-processing.md`  
**架构基础**: LangGraph (状态机编排) + State as Config (策略即状态) + Multi-Channel (多租户隔离)

---

## 任务目标

作为资深系统架构师，需要：

1. **系统性理解**：掌握整体架构、模块职责、数据流、控制流
2. **设计模式识别**：识别使用的设计模式、架构模式、最佳实践
3. **依赖关系分析**：理解模块间依赖、接口契约、数据传递
4. **质量评估**：评估代码质量、测试覆盖、可维护性、可扩展性
5. **风险识别**：识别性能瓶颈、安全风险、单点故障、扩展限制
6. **优化建议**：提出架构优化、性能优化、测试增强建议

---

## 分析框架

### 第一层：系统概览与核心设计理念

**需要回答的问题：**

1. **系统定位与规模**
   - 系统要解决什么业务问题？（100TB 规模、多模态、多租户 RAG）
   - 核心性能指标是什么？（P95 < 1.5s、可用性 ≥ 99.9%）
   - 业务约束是什么？（数据隔离、配置独立、权限控制）

2. **核心设计理念**
   - **State as Config**: 如何通过 LangGraph State 传递策略配置？优势与挑战？
   - **Multi-Modal First**: 如何统一处理文本/图片/表格？路由策略如何设计？
   - **Production-Grade**: 如何保证 100TB 规模下的性能与可靠性？

3. **架构分层**
   - Channel-KB-Chat 三层架构如何实现数据隔离？
   - 摄取管道（Ingestion）与检索管道（Retrieval）如何分离？
   - 存储层（Vector/Keyword/Blob）如何抽象与统一？

**分析方法：**
- 阅读 `docs/tech/system-design.md` 第 1-3 章
- 查看 `core/state.py` 理解状态定义
- 查看 `core/graph.py` 和 `core/ingestion/graph.py` 理解 LangGraph 编排

---

### 第二层：核心模块深度分析

#### 2.1 摄取管道 (Ingestion Pipeline)

**模块路径**: `core/ingestion/**`

**需要分析的内容：**

1. **数据流分析**
   ```
   Loader → Router → Parser (CPU/GPU) → Chunker → Embedder → Indexer → Finalizer
   ```
   - 每个节点的输入/输出 State 结构
   - 节点间的条件路由逻辑（Router 如何决定 CPU vs GPU）
   - 错误处理与重试机制（ErrorHandler 如何工作）

2. **关键设计决策**
   - **大文件处理**: `LoaderNode` 如何实现 lazy loading？流式处理如何避免 OOM？
   - **扫描 PDF 检测**: `RouterNode` 如何检测扫描件？fallback 策略是什么？
   - **多 Provider 支持**: `GpuVisionParser` 如何实现 OCR provider 工厂模式？fallback 链如何工作？
   - **分块策略**: `SmartChunker` 如何支持 fixed/semantic/layout_aware/table_first 四种模式？
   - **批量嵌入**: `BatchEmbedder` 如何实现批处理优化？缓存策略是什么？

3. **多租户隔离**
   - `channel_id` 如何在 State 中传递？
   - 集合命名如何隔离（`channel_collection_name`）？
   - 索引时如何确保数据隔离？

**分析方法：**
- 阅读 `core/ingestion/graph.py` 理解图编排
- 阅读各 Node 实现（`loader.py`, `router.py`, `parser/`, `chunker.py`, `embedder.py`, `indexer.py`）
- 查看测试文件 `tests/core/ingestion/**` 理解预期行为

**关键问题：**
- ZIP 炸弹防护是否实现？解压大小限制？
- 临时文件清理机制是否完善？
- 多模态索引（`*_images`, `*_tables`）命名是否一致？

---

#### 2.2 检索管道 (Retrieval Pipeline)

**模块路径**: `core/retrieval/**`

**需要分析的内容：**

1. **数据流分析**
   ```
   Router → Semantic Cache → Preprocessor → Retriever → Reranker → Generator → Hallucination Checker
   ```
   - 条件路由：`skip_retrieval` 如何跳过检索？
   - 缓存命中：Semantic Cache 如何工作？TTL 与 LRU 策略？
   - 意图识别：Preprocessor 如何识别 table_query/image_query/web_search？
   - 混合检索：Hybrid Retriever 如何融合 Vector + Keyword？RRF 算法实现？
   - 幻觉检测：Hallucination Checker 如何降权/重试？

2. **关键设计决策**
   - **语义缓存**: `SemanticCache` 如何计算相似度？hash 冲突如何处理？
   - **多模态检索**: `MultimodalRetriever` 如何查询 image/table 集合？集合不存在时如何降级？
   - **跨模态权重**: 图像/表格结果如何应用 `cross_modal_weight`？
   - **多租户过滤**: RRF 融合前如何过滤 channel_id？跨租户数据如何防止泄露？

3. **性能优化**
   - Reranker 异步包装如何避免阻塞事件循环？
   - 批量检索如何优化？
   - 缓存命中率如何提升？

**分析方法：**
- 阅读 `core/retrieval/graph.py` 理解检索图编排
- 阅读各 Node 实现（`preprocessor.py`, `retriever.py`, `reranker.py`, `generator.py`, `semantic_cache.py`）
- 阅读 `core/retrieval/multimodal/retriever.py` 理解多模态检索
- 查看测试文件 `tests/core/retrieval/**` 理解预期行为

**关键问题：**
- 缓存命中后是否真的跳过检索？（`skip_retrieval` 路径）
- 多租户隔离是否在所有检索路径生效？
- 存储不可用时的降级策略是什么？

---

#### 2.3 存储层 (Storage Layer)

**模块路径**: `core/storage/**`

**需要分析的内容：**

1. **存储抽象**
   - `VectorStore`: Qdrant 客户端封装，如何支持连接池？批量写入优化？
   - `KeywordStore`: Elasticsearch 客户端封装，如何支持重试？
   - `BlobStore`: 对象存储抽象，如何支持流式读写？

2. **多租户支持**
   - `channel_utils.py`: 如何生成隔离的集合/索引名？
   - `validate_channel_access`: 如何验证跨租户访问？
   - `index_router.py`: `list_kb_chunks`/`scroll_kb_chunks` 如何支持分页与过滤？

3. **配置管理**
   - `kb_config.py`: KB 配置如何存储与加载？
   - `config_store.py`: 策略配置如何持久化？

**分析方法：**
- 阅读 `core/storage/vector_store.py`, `keyword_store.py`, `blob_store.py`
- 阅读 `core/storage/channel_utils.py` 理解多租户工具
- 阅读 `core/storage/index_router.py` 理解分页 API

**关键问题：**
- 连接池管理是否完善？高并发下是否可能连接耗尽？
- 批量写入失败时的重试机制？
- 维度不匹配时的处理策略？

---

#### 2.4 高级算法 (Advanced Algorithms)

**模块路径**: `core/algorithms/**`

**需要分析的内容：**

1. **RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval)**
   - `raptor_deep.py`: 如何递归聚类与摘要？
   - `raptor_light.py`: 轻量级实现差异？
   - 如何支持 channel_id 过滤与分页？

2. **GraphRAG**
   - `graphrag_deep.py`: 如何提取实体与关系？社区检测如何工作？
   - `graphrag_light.py`: 轻量级实现差异？
   - 图存储如何持久化？

3. **MindMap**
   - `mindmap_light.py`: 思维导图生成逻辑？

**分析方法：**
- 阅读各算法实现文件
- 查看 `core/storage/index_router.py` 中的 `scroll_kb_chunks` API
- 查看测试文件 `tests/core/algorithms/**`

**关键问题：**
- 大数据集（>50000 chunks）时的内存管理？
- channel_id 过滤是否在所有算法路径生效？
- 算法结果如何持久化与版本管理？

---

#### 2.5 多模态处理 (Multimodal Processing)

**模块路径**: `core/retrieval/multimodal/`, `core/vision/`

**需要分析的内容：**

1. **多模态检索**
   - `MultimodalRetriever`: 如何统一检索文本/图片/表格？
   - 集合命名一致性：`*_images`, `*_tables` 如何创建与查询？
   - 跨模态权重如何应用？

2. **多模态嵌入**
   - `MultimodalEmbedder`: 如何统一嵌入文本/图片/表格？
   - CLIP 模型缓存策略？
   - LRU+TTL 缓存实现？

3. **视觉处理**
   - `layout_analyzer.py`: 版面分析如何工作？
   - `yolo_detector.py`: YOLO 检测如何与 OCR 结合？
   - `table.py`: 表格提取逻辑？

**分析方法：**
- 阅读 `core/retrieval/multimodal/retriever.py`, `embedder.py`
- 阅读 `core/vision/**` 各文件
- 查看测试文件 `tests/core/retrieval/test_multimodal*.py`

**关键问题：**
- 集合不存在时的降级策略？
- 显存不足时的 fallback？
- 缓存命中率如何提升？

---

#### 2.6 配置与状态管理 (State & Config)

**模块路径**: `core/state.py`

**需要分析的内容：**

1. **StrategyConfig**
   - 平铺 vs 嵌套配置兼容性：`chunking_mode` vs `chunking.mode`
   - Effective 属性逻辑：优先级与回退
   - 边界值处理：falsy 值（0, False）不应被当作 None

2. **TypedDict 状态**
   - `IngestState`: 摄取管道状态结构
   - `RetrievalState`: 检索管道状态结构
   - `ProcessedChunk`, `ChunkMetadata`: 数据结构定义

3. **多租户支持**
   - `channel_id` 必填验证（静态类型 vs 运行时验证）
   - 空字符串处理策略

**分析方法：**
- 阅读 `core/state.py` 完整实现
- 查看测试文件 `tests/core/state/**` 理解边界情况

**关键问题：**
- 运行时 channel_id 验证是否完善？
- 配置序列化/反序列化一致性？
- 向后兼容性如何保证？

---

### 第三层：设计模式与架构决策

**需要识别的内容：**

1. **设计模式**
   - **工厂模式**: OCR Provider 工厂（`GpuVisionParser`）
   - **策略模式**: 分块策略（`SmartChunker`）
   - **观察者模式**: 进度通知（SSE）
   - **适配器模式**: 存储抽象（`VectorStore`, `KeywordStore`, `BlobStore`）
   - **单例模式**: 模型缓存（CLIP, CrossEncoder）

2. **架构模式**
   - **管道模式**: LangGraph StateGraph 编排
   - **状态机模式**: 处理阶段转换（upload → parse → chunk → embed → index）
   - **事件驱动**: SSE 进度推送
   - **分层架构**: 存储层/业务层/API 层

3. **最佳实践**
   - **依赖注入**: CapabilityLoader
   - **配置外化**: State as Config
   - **错误处理**: ErrorHandler + Retry
   - **可观测性**: OTel + Prometheus

**分析方法：**
- 代码审查：识别模式使用
- 设计文档对比：验证实现与设计一致性
- 测试覆盖分析：模式是否正确测试

---

### 第四层：依赖关系与接口契约

**需要分析的内容：**

1. **模块依赖图**
   ```
   ingestion/ → state, storage, embedding, llm, vision
   retrieval/ → state, storage, embedding, llm, reranker
   algorithms/ → state, storage, llm
   storage/ → (外部服务: Qdrant, ES, MinIO)
   ```

2. **接口契约**
   - Node 接口：`async def __call__(self, state: IngestState/RetrievalState) -> State`
   - 存储接口：`VectorStore.search()`, `KeywordStore.search()`, `BlobStore.get()`
   - LLM 接口：`LLMGateway.chat()`

3. **数据传递**
   - State 如何在节点间传递？
   - 错误如何传播（`error_log`）？
   - 进度如何更新（`progress`）？

**分析方法：**
- 绘制依赖图（可使用工具或手动）
- 分析接口定义与使用
- 检查循环依赖

---

### 第五层：测试覆盖与质量评估

**需要分析的内容：**

1. **测试覆盖分析**
   - 单元测试：各模块是否有对应测试？
   - 集成测试：端到端场景是否覆盖？
   - 性能测试：大文件、并发场景是否测试？

2. **测试质量评估**
   - 测试用例是否覆盖边界情况？
   - Mock 策略是否合理？
   - 断言是否充分？

3. **覆盖缺口识别**
   - 参考之前的审查报告（`tests/core/ingestion/FINAL_TEST_REPORT.md`）
   - 识别高风险未覆盖场景

**分析方法：**
- 查看 `tests/core/**` 目录结构
- 运行覆盖率报告：`pytest --cov=core --cov-report=html`
- 对比审查报告中的缺口清单

---

### 第六层：性能与可扩展性分析

**需要分析的内容：**

1. **性能瓶颈识别**
   - 同步阻塞：Reranker 是否异步化？
   - 批量处理：Embedder 批处理大小是否优化？
   - 缓存策略：语义缓存、嵌入缓存命中率？
   - 数据库连接：连接池大小是否合理？

2. **可扩展性评估**
   - 水平扩展：无状态节点是否支持多实例？
   - 垂直扩展：单机资源限制（内存、GPU）？
   - 存储扩展：100TB 规模下的分片策略？

3. **资源管理**
   - 内存管理：大文件 lazy loading，临时文件清理
   - GPU 管理：模型缓存，显存检查
   - 连接管理：连接池，超时设置

**分析方法：**
- 代码审查：识别同步调用、资源泄漏
- 性能测试：查看 `tests/core/performance/**`
- 监控指标：查看 `core/utils/monitor.py` 定义的指标

---

### 第七层：安全与可靠性分析

**需要分析的内容：**

1. **多租户安全**
   - channel_id 验证是否在所有路径生效？
   - 跨租户数据泄露风险点？
   - 集合命名隔离是否完善？

2. **错误处理**
   - 异常是否被正确捕获？
   - 降级策略是否完善？
   - 重试机制是否合理？

3. **数据一致性**
   - 批量写入失败时的处理？
   - 事务支持？
   - 幂等性保证？

**分析方法：**
- 代码审查：查找 channel_id 使用点
- 测试审查：查找安全测试用例
- 风险分析：识别单点故障

---

## 输出要求

### 1. 架构理解报告（核心输出）

**格式：Markdown 文档**

**必须包含的章节：**

1. **执行摘要**（1 页）
   - 系统定位、核心价值、关键指标
   - 架构亮点与创新点
   - 主要风险与改进建议（Top 5）

2. **系统架构全景**（3-5 页）
   - 整体架构图（文字描述或 ASCII 图）
   - 核心模块职责与关系
   - 数据流与控制流
   - 关键设计决策与理由

3. **模块深度分析**（10-15 页）
   - 每个核心模块的详细分析
   - 设计模式识别
   - 接口契约与依赖关系
   - 关键实现细节

4. **质量评估**（3-5 页）
   - 代码质量评估（可读性、可维护性、可扩展性）
   - 测试覆盖分析（覆盖率、缺口、质量）
   - 性能与可扩展性评估
   - 安全与可靠性评估

5. **风险与优化建议**（3-5 页）
   - 高风险问题清单（P0/P1/P2）
   - 性能瓶颈与优化建议
   - 架构改进建议
   - 测试增强建议

6. **附录**
   - 依赖关系图
   - 关键代码片段引用
   - 参考文档索引

### 2. 关键问题清单

**格式：结构化列表**

对每个识别的关键问题，提供：
- 问题描述
- 影响范围（模块、功能）
- 严重级别（P0/P1/P2）
- 根因分析
- 修复建议
- 相关代码路径

### 3. 架构优化路线图

**格式：时间线 + 优先级**

- 短期（1-2 周）：P0 问题修复
- 中期（1-2 月）：P1 优化与测试增强
- 长期（3-6 月）：架构演进与性能优化

---

## 分析方法论

### 步骤 1：文档先行
1. 阅读 `docs/tech/system-design.md` 理解设计意图
2. 阅读 `docs/tech/implementation_plan.md` 理解实现计划
3. 阅读 `docs/tech/large-pdf-processing.md` 理解大文件处理策略

### 步骤 2：代码探索
1. 从入口点开始：`core/graph.py`, `core/ingestion/graph.py`
2. 追踪数据流：State 如何在节点间传递
3. 理解控制流：条件路由、错误处理、重试机制
4. 识别设计模式：工厂、策略、适配器等

### 步骤 3：测试验证
1. 查看测试文件理解预期行为
2. 运行测试验证当前实现
3. 分析测试覆盖缺口

### 步骤 4：深度分析
1. 绘制依赖关系图
2. 识别性能瓶颈
3. 评估安全风险
4. 分析可扩展性

### 步骤 5：综合评估
1. 对比设计与实现
2. 识别偏差与风险
3. 提出优化建议

---

## 关键检查点

### 必须回答的问题：

1. **架构一致性**
   - 实现是否与设计文档一致？
   - 设计决策是否被正确实现？
   - 是否有偏离设计的实现？

2. **多租户隔离**
   - channel_id 验证是否完善？
   - 数据隔离是否在所有路径生效？
   - 跨租户访问风险点在哪里？

3. **性能与可扩展性**
   - 100TB 规模下的瓶颈在哪里？
   - 水平扩展能力如何？
   - 资源管理是否完善？

4. **可靠性**
   - 错误处理是否完善？
   - 降级策略是否合理？
   - 单点故障在哪里？

5. **测试质量**
   - 测试覆盖是否充分？
   - 高风险场景是否测试？
   - 测试质量是否达标？

---

## 工具与资源

### 推荐工具：
- **代码分析**: `pytest --cov`, `mypy`, `pylint`
- **依赖分析**: `pipdeptree`, 手动绘制依赖图
- **性能分析**: `cProfile`, `memory_profiler`
- **文档生成**: Markdown, Mermaid 图表

### 参考文档：
- `docs/tech/system-design.md` - 系统设计文档
- `docs/tech/implementation_plan.md` - 实现计划
- `docs/tech/large-pdf-processing.md` - 大文件处理
- `tests/core/**/FINAL_TEST_REPORT.md` - 测试审查报告

---

## 成功标准

**完成本 Prompt 后，应该能够：**

1. ✅ 清晰描述系统整体架构与核心模块职责
2. ✅ 理解关键设计决策与实现细节
3. ✅ 识别设计模式与架构模式的使用
4. ✅ 评估代码质量、测试覆盖、性能、安全性
5. ✅ 提出具体的优化建议与改进路线图
6. ✅ 回答关于系统架构的任何深入问题

---

_生成时间: 2025-12-12_  
_适用版本: OmniRAG v2.0+_

