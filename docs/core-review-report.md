# Core 目录代码审查报告

> **版本**: v1.0
> **日期**: 2025-12-08
> **审查范围**: `/core/` 目录下所有 56 个 Python 文件
> **对齐文档**: `docs/architecture.md`, `docs/tech/system-design.md`, `docs/api-spec.md`

---

## 1. 审查结论摘要

### 1.1 总体评估

| 评估维度 | 评分 | 说明 |
|:---------|:----:|:-----|
| **代码结构** | ⭐⭐⭐⭐ | 模块划分清晰，职责分离合理 |
| **设计对齐** | ⭐⭐⭐⭐ | 已支持 Multi-Channel/Multi-KB 架构 |
| **代码质量** | ⭐⭐⭐ | 大部分实现完整，少数需补充 |
| **性能优化** | ⭐⭐⭐⭐ | Singleton/LRU 缓存已实现 |
| **错误处理** | ⭐⭐⭐ | 有防御性编程，但可进一步增强 |
| **可测试性** | ⭐⭐ | 缺少单元测试 |

### 1.2 文件统计

| 目录 | 文件数 | 状态 |
|:-----|:------:|:----:|
| `core/` (根) | 3 | ✅ |
| `core/algorithms/` | 5 | ✅ |
| `core/embedding/` | 3 | ✅ |
| `core/ingestion/` | 10 | ✅ |
| `core/llm/` | 2 | ✅ |
| `core/model_gateway/` | 1 | ⚠️ 可合并 |
| `core/pipeline/` | 4 | ⚠️ 可精简 |
| `core/reranker/` | 4 | ✅ |
| `core/retrieval/` | 5 | ✅ |
| `core/storage/` | 7 | ✅ |
| `core/tools/` | 3 | ✅ |
| `core/utils/` | 2 | ✅ |
| `core/vision/` | 4 | ✅ |
| **总计** | **56** | |

---

## 2. 核心文件审查

### 2.1 `core/state.py` ✅

**状态**: 已对齐设计文档

**内容**:
- `ChunkMetadata` - 包含 `channel_id` ✅
- `IngestState` - 包含 `channel_id` ✅
- `RetrievalState` - 包含 `channel_id`, `session_id`, `kb_names` ✅
- `StrategyConfig` - 完整策略配置 ✅

**评估**: 符合 Multi-Channel 架构要求

### 2.2 `core/graph.py` ✅

**状态**: V4 纯实现

**内容**:
- `IntentRouter` - 意图路由 (关键词匹配)
- `WebSearchNode` - 网络搜索集成
- `HallucinationChecker` - 幻觉检测 (TODO 占位)
- `create_graph()` - 主 RAG 图

**改进建议**:
- `IntentRouter` 应升级为 LLM 驱动 (P2)
- `HallucinationChecker` 需完整实现 (P2)

---

## 3. 模块审查

### 3.1 `algorithms/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `raptor_deep.py` | ✅ | 完整实现：K-Means 聚类 + LLM 摘要 |
| `raptor_light.py` | ✅ | 复用 deep 核心，调整参数 |
| `graphrag_deep.py` | ✅ | 完整实现：实体/关系提取 + 图存储 |
| `graphrag_light.py` | ✅ | 复用 deep 核心，限制实体类型 |
| `mindmap_light.py` | ✅ | LLM 驱动主题提取 |

**设计亮点**:
- Light 版本复用 Deep 核心算法
- 并发控制 (`Semaphore`)
- 错误容忍 (单个失败不中断)

**改进建议**:
- GraphRAG 添加 Louvain 社区检测 (P2)

### 3.2 `embedding/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `registry.py` | ✅ | 工厂模式，支持 simple/auto |
| `provider_embedder.py` | ✅ | DB 驱动，支持 DashScope/OpenAI |
| `simple_embedder.py` | ✅ | 基于 hash 的简单嵌入 (开发用) |

**设计亮点**:
- 异步批处理 (`embed_batch`)
- Prometheus 监控指标
- DB 配置热加载

### 3.3 `ingestion/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `graph.py` | ✅ | LangGraph 摄取管道 |
| `nodes/loader.py` | ✅ | Blob 存储读取 |
| `nodes/router.py` | ✅ | CPU/GPU 路由决策 |
| `nodes/parser/cpu_parser.py` | ✅ | PDF/HTML/MD/EML 解析 |
| `nodes/parser/gpu_parser.py` | ✅ | VLM OCR (DeepSeek/Qwen/Volc/YOLO) |
| `nodes/chunker.py` | ✅ | 3 种模式：fixed/table_first/layout_aware |
| `nodes/embedder.py` | ✅ | 批量嵌入 + 进度跟踪 |
| `nodes/indexer.py` | ✅ | Qdrant + ES 双写 |
| `nodes/image_captioner.py` | ⚠️ | VLM 调用未完整实现 |

**设计亮点**:
- OCR 降级链 (qwen-vl → volc → paddle → mock)
- 分批索引避免超时
- 错误日志记录

**改进建议**:
- `image_captioner.py` 需完整 VLM 调用 (P2)
- 添加 `docx`/`pptx` 解析支持 (P2)

### 3.4 `retrieval/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `graph.py` | ✅ | QA 图定义 (循环纠正) |
| `nodes/preprocessor.py` | ✅ | Intent + Query Rewrite (LLM) |
| `nodes/retriever.py` | ✅ | 向量 + 关键词 + RRF 融合 |
| `nodes/reranker.py` | ✅ | CrossEncoder + DB 配置 |
| `nodes/generator.py` | ✅ | Citation 生成 (XML 标签) |

**设计亮点**:
- 支持 Multi-KB 检索 (`kb_names` 列表)
- Intent 过滤 (table_query → block_type=table)
- RRF 融合算法

**设计对齐**:
- ✅ 符合 `system-design.md` 检索管道设计

### 3.5 `storage/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `vector_store.py` | ✅ | Qdrant 客户端 (Singleton) |
| `keyword_store.py` | ✅ | ES 客户端 (Singleton) |
| `blob_store.py` | ✅ | Local/OSS/MinIO 支持 |
| `checkpoint.py` | ✅ | LangGraph 检查点 (可选) |
| `kb_config.py` | ✅ | KB 配置管理 (DB + 文件回退) |
| `kb_config_db.py` | ✅ | KB 配置 DB 操作 |
| `index_router.py` | ⚠️ | 部分函数是 Stub |
| `config_store.py` | ✅ | 存储配置 DB 读取 |

**设计亮点**:
- 3 种 Blob 存储实现 (可扩展)
- KB 配置支持 DB + 文件双回退
- Singleton 模式避免重复连接

**改进建议**:
- `index_router.py` 的 `list_all_meta()` 需完整实现 (P1)
- 添加 Channel 前缀隔离 (P0)

### 3.6 `reranker/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `cross_encoder.py` | ✅ | Singleton + Fallback |
| `cohere_reranker.py` | ✅ | Cohere API |
| `http_reranker.py` | ✅ | 通用 HTTP Reranker |
| `registry.py` | ✅ | DB 驱动选择 + 降级链 |

**设计亮点**:
- Singleton 模式避免重复加载模型
- Token Overlap 回退算法
- HTTP 重试 + 线性退避

### 3.7 `llm/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `gateway.py` | ✅ | DB 驱动 + 熔断 + 降级 |
| `registry.py` | ✅ | 工厂包装器 |

**设计亮点**:
- Circuit Breaker (3 次失败 → 30s 冷却)
- 用量记录 (usage.jsonl)
- 降级链 (`fallback_models`)

**设计对齐**:
- ✅ 符合 `system-design.md` 熔断/降级设计

### 3.8 `tools/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `web_search_provider.py` | ✅ | 4 种搜索引擎 (DuckDuckGo/Tavily/Serper/Bocha) |
| `web_search_registry.py` | ✅ | 工厂模式 + DB 配置 |
| `config_store.py` | ✅ | Web Search 配置 DB 读取 |

**设计亮点**:
- Circuit Breaker 内置
- Prometheus 监控
- 自动选择可用 Provider

### 3.9 `vision/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `layoutlm_parser.py` | ✅ | LRU 缓存模型加载 |
| `yolo_detector.py` | ✅ | LRU 缓存模型加载 |
| `layout_analyzer.py` | ✅ | OpenCV 版面分割 |
| `table.py` | ✅ | Markdown 表格提取 |

**设计亮点**:
- LRU 缓存避免重复加载模型
- OpenCV 轻量版面分析

### 3.10 `pipeline/` ⚠️

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `builder.py` | ⚠️ | 仅 7 行，可合并 |
| `kb_merge.py` | ✅ | KB 参数合并逻辑 |
| `rag_scenarios.py` | ⚠️ | 静态数据，可移至配置 |
| `registry.py` | ⚠️ | 静态数据，可移至配置 |

**改进建议**:
- 合并 `builder.py` 到 `ingestion/graph.py`
- `rag_scenarios.py` 和 `registry.py` 可移至 DB 或配置文件

### 3.11 `model_gateway/` ⚠️

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `config_store.py` | ⚠️ | 与 `llm/gateway.py` 功能重叠 |

**改进建议**:
- 合并到 `llm/` 或 `storage/` 目录

### 3.12 `utils/` ✅

| 文件 | 状态 | 说明 |
|:-----|:----:|:-----|
| `monitor.py` | ✅ | Prometheus + OpenTelemetry 配置 |
| `trace.py` | ✅ | Span 属性设置工具 |

---

## 4. 设计对齐检查

### 4.1 与 `architecture.md` 对齐

| 设计要求 | 实现状态 | 位置 |
|:---------|:--------:|:-----|
| Multi-Channel 架构 | ✅ | `state.py` |
| Channel-KB-Chat 三层模型 | ✅ | `state.py` |
| Session-KB 多对多绑定 | ✅ | `kb_names: List[str]` |
| State as Config | ✅ | `StrategyConfig` |
| Singleton 模型加载 | ✅ | `reranker/`, `vision/` |

### 4.2 与 `system-design.md` 对齐

| 设计要求 | 实现状态 | 位置 |
|:---------|:--------:|:-----|
| Ingestion 管道 | ✅ | `ingestion/graph.py` |
| Retrieval 管道 | ✅ | `retrieval/graph.py` |
| RRF 融合 | ✅ | `retrieval/nodes/retriever.py` |
| RAPTOR 算法 | ✅ | `algorithms/raptor_deep.py` |
| GraphRAG 算法 | ✅ | `algorithms/graphrag_deep.py` |
| LLM 熔断/降级 | ✅ | `llm/gateway.py` |
| Web Search 集成 | ✅ | `tools/web_search_*.py` |

### 4.3 与 `api-spec.md` 对齐

| API 要求 | 实现状态 | 说明 |
|:---------|:--------:|:-----|
| Channel 管理 | ⚠️ | State 已支持，API 待实现 |
| KB 管理 | ✅ | `storage/kb_config*.py` |
| 文档摄取 | ✅ | `ingestion/` |
| Chat 检索 | ✅ | `retrieval/` |
| 文件管理 (OSS) | ⚠️ | `storage/blob_store.py` 已实现，API 待暴露 |

---

## 5. 问题与风险

### 5.1 高优先级 (P0)

| 问题 | 影响 | 建议 |
|:-----|:-----|:-----|
| Channel 数据隔离未实现 | 不同 Channel 数据可交叉访问 | Storage 层添加 channel 前缀 |
| `index_router.py` 部分 Stub | 功能不完整 | 完整实现 `list_all_meta()` |

### 5.2 中优先级 (P1)

| 问题 | 影响 | 建议 |
|:-----|:-----|:-----|
| 无单元测试 | 回归风险 | 添加 pytest 测试套件 |
| `image_captioner.py` 未完整 | VLM 功能受限 | 完成 VLM 调用实现 |
| `pipeline/` 目录冗余 | 维护成本 | 合并/精简 |

### 5.3 低优先级 (P2)

| 问题 | 影响 | 建议 |
|:-----|:-----|:-----|
| `IntentRouter` 仅关键词匹配 | 意图识别准确率低 | 升级为 LLM 驱动 |
| `HallucinationChecker` 占位 | 幻觉检测不生效 | 完整实现 |
| GraphRAG 无社区检测 | 知识图谱分析能力弱 | 添加 Louvain 算法 |

---

## 6. 改进路线图

### Phase 1: 安全与隔离 (P0)

```
1. storage/vector_store.py - 添加 channel_id 前缀到 collection_name
2. storage/keyword_store.py - 添加 channel_id 前缀到 index_name
3. storage/index_router.py - 完整实现 list_all_meta()
```

### Phase 2: 功能补全 (P1)

```
1. ingestion/nodes/image_captioner.py - 完整 VLM 调用
2. 合并 pipeline/builder.py 到 ingestion/
3. 添加 pytest 测试框架
```

### Phase 3: 能力增强 (P2)

```
1. graph.py - IntentRouter 升级为 LLM 驱动
2. graph.py - HallucinationChecker 完整实现
3. algorithms/graphrag_deep.py - 添加 Louvain 社区检测
```

---

## 7. 可信度声明

基于本次审查，**core 目录代码可信**，具备以下特点：

1. **架构清晰**: 模块职责分离，依赖关系明确
2. **设计对齐**: 已实现 Multi-Channel/Multi-KB 核心架构
3. **防御性编程**: 错误处理 + 降级机制
4. **性能优化**: Singleton/LRU 缓存已实现
5. **待改进**: Channel 隔离、部分 Stub 实现、测试覆盖

**建议**: 在完成 P0 任务后，core 目录可作为生产环境的可靠基础。

---

*审查人: Antigravity Agent*
*审查时间: 2025-12-08T14:00:00+09:00*
