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

### P3.3 能力模块实现 ✅
| 子任务 | 状态 | 文件 |
|:-------|:----:|:-----|
| 表格提取能力 (TableExtractor) | ✅ | `core/ingestion/nodes/table_extractor.py` |
| 视频理解能力 (VideoProcessor) | ✅ | `core/ingestion/processors/video_processor.py` |
| Excel 分析能力 (ExcelProcessor) | ✅ | `core/ingestion/processors/excel_processor.py` |
| 版面分析能力 (LayoutAnalyzer) | ✅ | `core/vision/layout_analyzer.py` |
| 漫画识别能力 (ComicProcessor) | ✅ | `core/ingestion/processors/comic_processor.py` |
| 多模态检索能力 | ✅ | `core/retrieval/multimodal/` |

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
| 2025-12-09 | P3.3 能力模块 | 6个能力模块全部实现 (表格/视频/Excel/版面/漫画/多模态) |

---

## 🎉 P3.3 能力模块实现完成！

### ✅ 已完成
- **P0-P2**: Core 目录重构全部完成
- **P3.1**: 能力框架基础设施 (manifest, registry, loader, API)
- **P3.2**: 状态集成 (IngestState/RetrievalState + capability_loader)
- **P3.3**: 能力模块实现 (6/6 完成)

### 🔄 进行中
- **P3.4**: 相关文档更新

### 📦 新增能力模块

| 模块 | 文件 | 功能 |
|:-----|:-----|:-----|
| **TableExtractor** | `core/ingestion/nodes/table_extractor.py` | 表格识别 (TableTransformer/PP-Structure/Camelot) |
| **VideoProcessor** | `core/ingestion/processors/video_processor.py` | 视频关键帧+Whisper转写+VLM描述 |
| **ExcelProcessor** | `core/ingestion/processors/excel_processor.py` | 多Sheet解析+公式理解+关系检测 |
| **LayoutAnalyzer** | `core/vision/layout_analyzer.py` | 版面分析+阅读顺序检测 |
| **ComicProcessor** | `core/ingestion/processors/comic_processor.py` | 漫画分格+气泡OCR+场景描述 |
| **MultimodalRetriever** | `core/retrieval/multimodal/` | 文本+图像+表格联合检索 |

### 📁 完整文件结构

```
core/
├── capabilities/
│   ├── __init__.py        # 模块导出
│   ├── manifest.yaml      # 17项能力定义
│   ├── registry.py        # 能力注册表
│   └── loader.py          # 能力加载器
├── ingestion/
│   ├── nodes/
│   │   └── table_extractor.py  # 表格提取 ✨
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── comic_processor.py  # 漫画识别 ✨
│   │   ├── excel_processor.py  # Excel分析 ✨
│   │   └── video_processor.py  # 视频理解 ✨
│   └── state_factory.py
├── retrieval/
│   └── multimodal/
│       ├── __init__.py
│       ├── embedder.py    # 多模态嵌入 ✨
│       └── retriever.py   # 多模态检索 ✨
├── vision/
│   ├── __init__.py
│   └── layout_analyzer.py # 版面分析 ✨
└── state.py               # 添加 capability_loader 字段

server/capability_routes.py  # 能力 API (12个端点)
```

### 🎯 下一步
1. 完善文档 (P3.4)
2. 前端开发能力配置 UI
3. 集成测试
