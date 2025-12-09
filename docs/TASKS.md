# Core 重构任务清单

> **来源**: `docs/core-review-report.md`
> **创建**: 2025-12-08
> **状态跟踪**: ✅ 完成 | 🔄 进行中 | ⬜ 待办

---

## P0 任务 (安全与隔离)

### P0.1 Channel 数据隔离 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 创建 channel_utils 工具模块 | ✅ | `core/storage/channel_utils.py` |
| Vector Store 添加 channel_id 前缀 | ✅ | `core/ingestion/nodes/indexer.py` |
| Keyword Store 添加 channel_id 前缀 | ✅ | `core/ingestion/nodes/indexer.py` |
| Retriever 使用 channel 前缀 | ✅ | `core/retrieval/nodes/retriever.py` |

### P0.2 Stub 实现补全 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| `list_all_meta()` 完整实现 | ✅ | `core/storage/index_router.py` |
| `list_collections_info()` 完整实现 | ✅ | `core/storage/index_router.py` |
| `list_page_meta()` 完整实现 | ✅ | `core/storage/index_router.py` |
| `doc_stats()` 完整实现 | ✅ | `core/storage/index_router.py` |
| `get_collection_stats()` 新增 | ✅ | `core/storage/index_router.py` |

---

## P1 任务 (功能补全)

### P1.1 VLM 功能 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| `ImageCaptioner` VLM 调用完整实现 | ✅ | `core/ingestion/nodes/image_captioner.py` |

### P1.2 代码整理 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 删除未使用的 `builder.py` | ✅ | `core/pipeline/builder.py` (已删除) |
| 移动配置到 llm/ | ✅ | `core/llm/provider_config.py` |
| 删除 `model_gateway/` 目录 | ✅ | `core/model_gateway/` (已删除) |

### P1.3 测试覆盖 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 添加 pytest 配置 | ✅ | `pytest.ini` |
| 添加共享 fixtures | ✅ | `tests/conftest.py` |
| channel_utils 单元测试 | ✅ | `tests/core/test_channel_utils.py` |
| state 模块单元测试 | ✅ | `tests/core/test_state.py` |

---

## P2 任务 (能力增强)

### P2.1 智能化升级 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| IntentRouter 升级为 LLM 驱动 | ✅ | `core/graph.py` |
| HallucinationChecker 完整实现 | ✅ | `core/graph.py` |

### P2.2 算法增强 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| GraphRAG 添加 Louvain 社区检测 | ✅ | `core/algorithms/graphrag_deep.py` |
| 社区摘要生成 | ✅ | `core/algorithms/graphrag_deep.py` |

### P2.3 解析能力扩展 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 添加 docx 解析支持 | ✅ | `core/ingestion/nodes/parser/cpu_parser.py` |
| 添加 pptx 解析支持 | ✅ | `core/ingestion/nodes/parser/cpu_parser.py` |
| 表格提取 (DOCX/PPTX) | ✅ | `core/ingestion/nodes/parser/cpu_parser.py` |

---

## 完成记录

| 日期 | 任务 | 备注 |
|:-----|:-----|:-----|
| 2025-12-08 | 创建任务清单 | 从 core-review-report.md 提取 |
| 2025-12-08 | P0.1 Channel 数据隔离 | 创建 channel_utils.py，更新 indexer/retriever |
| 2025-12-08 | P0.2 Stub 实现补全 | index_router.py 完整实现 |
| 2025-12-08 | P1.1 VLM 功能 | ImageCaptioner 完整实现 (DashScope/OpenAI/DeepSeek) |
| 2025-12-08 | P1.2 代码整理 | 移动 model_gateway 到 llm/，删除未用的 builder.py |
| 2025-12-08 | P1.3 测试覆盖 | pytest 框架 + 23 个单元测试 (全通过) |
| 2025-12-08 | P2.1 智能化升级 | IntentRouter LLM 驱动 + HallucinationChecker 完整实现 |
| 2025-12-08 | P2.2 算法增强 | GraphRAG Louvain 社区检测 + 摘要生成 |
| 2025-12-08 | P2.3 解析扩展 | DOCX + PPTX 解析支持 (含表格) |

---

## P3 任务 (能力产品化)

> **目标**: 让核心能力在 UI 中"可见、可选、可配、可用"

### P3.1 能力框架基础设施 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 创建能力清单 (manifest.yaml) | ✅ | `core/capabilities/manifest.yaml` |
| 创建能力注册表 | ✅ | `core/capabilities/registry.py` |
| 创建能力加载器 | ✅ | `core/capabilities/loader.py` |
| 创建 API 端点 | ✅ | `server/capability_routes.py` |
| KB 配置集成 capabilities 字段 | ✅ | `core/storage/kb_config.py` |

### P3.2 状态集成 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| IngestState 添加 capability_loader | ✅ | `core/state.py` |
| RetrievalState 添加 capability_loader | ✅ | `core/state.py` |
| 创建状态工厂函数 | ✅ | `core/ingestion/state_factory.py` |
| 更新 server/api/ingest.py | ✅ | `server/api/ingest.py` |
| 更新测试 fixtures | ✅ | `tests/conftest.py`, `tests/core/ingestion/test_chunker.py` |

### P3.3 能力模块实现 🔄
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 表格提取能力 (table_extractor) | ⬜ | `core/ingestion/nodes/table_extractor.py` |
| 视频理解能力 (video_processor) | ⬜ | `core/ingestion/processors/video_processor.py` |
| Excel 分析能力 (excel_analyzer) | ⬜ | `core/ingestion/nodes/excel_analyzer.py` |
| 多模态检索能力 | ⬜ | `core/retrieval/multimodal/` |

### P3.4 文档更新 ⬜
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 能力策略文档 | ✅ | `docs/product/capability-strategy.md` |
| 多模态处理文档更新 | 🔄 | `docs/tech/large-pdf-processing.md` |
| 架构文档更新 | ⬜ | `docs/architecture.md` |

---

## 完成记录

| 日期 | 任务 | 备注 |
|:-----|:-----|:-----|
| 2025-12-08 | 创建任务清单 | 从 core-review-report.md 提取 |
| 2025-12-08 | P0.1 Channel 数据隔离 | 创建 channel_utils.py，更新 indexer/retriever |
| 2025-12-08 | P0.2 Stub 实现补全 | index_router.py 完整实现 |
| 2025-12-08 | P1.1 VLM 功能 | ImageCaptioner 完整实现 (DashScope/OpenAI/DeepSeek) |
| 2025-12-08 | P1.2 代码整理 | 移动 model_gateway 到 llm/，删除未用的 builder.py |
| 2025-12-08 | P1.3 测试覆盖 | pytest 框架 + 23 个单元测试 (全通过) |
| 2025-12-08 | P2.1 智能化升级 | IntentRouter LLM 驱动 + HallucinationChecker 完整实现 |
| 2025-12-08 | P2.2 算法增强 | GraphRAG Louvain 社区检测 + 摘要生成 |
| 2025-12-08 | P2.3 解析扩展 | DOCX + PPTX 解析支持 (含表格) |
| 2025-12-08 | P3.1 能力框架 | manifest.yaml + registry + loader + API routes |
| 2025-12-08 | P3.2 状态集成 | IngestState/RetrievalState 集成 capability_loader |

---

## 当前进度总结

### ✅ 已完成
- **P0-P2**: Core 目录重构全部完成
- **P3.1-P3.2**: 能力产品化基础设施和状态集成完成

### 🔄 进行中
- **P3.3**: 能力模块的具体实现（表格提取、视频理解等）
- **P3.4**: 相关文档更新

### 📦 能力框架关键文件
```
core/capabilities/
├── __init__.py        # 模块导出
├── manifest.yaml      # 17项能力定义 (配置Schema、UI展示、依赖)
├── registry.py        # 能力注册表 (加载、查询、验证)
└── loader.py          # 能力加载器 (动态加载、状态追踪)

server/capability_routes.py  # 能力 API (12个端点)
core/ingestion/state_factory.py  # 状态工厂函数
```

### 🎯 下一步
1. 实现 `manifest.yaml` 中各能力对应的处理模块
2. 前端开发能力配置 UI
3. 完善文档
