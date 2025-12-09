# Core 能力产品化战略

> **版本**: v1.0
> **日期**: 2025-12-08
> **视角**: 产品经理 + 技术架构

---

## 1. 设计理念理解

### 1.1 核心原则

| 原则 | 含义 | 反模式 |
|:-----|:-----|:-------|
| **可见性** | 能力在 UI 中可发现、可理解 | 隐藏在代码深处，用户无感知 |
| **可配置** | KB 级别独立配置，灵活组合 | 全局配置，一刀切 |
| **场景化** | 能力与使用场景绑定 | 技术术语堆砌，用户不知何时用 |
| **即用性** | 配置即生效，无需重启/部署 | 改配置需发版 |
| **显化** | 能力分类清晰，状态可见 | 能力混杂，状态黑盒 |

### 1.2 避免的问题：能力沉默

```
❌ 沉默状态 (Silent Capability)
──────────────────────────────────────────────
• 代码中实现了表格识别，但用户不知道有这个功能
• 配置项存在但没有 UI 入口
• 能力就绪但无法触发
• 处理成功/失败无反馈

✅ 显化状态 (Visible Capability)
──────────────────────────────────────────────
• UI 能力卡片：图标 + 名称 + 描述 + 状态
• 配置面板：开关 + 参数 + 预览
• 使用入口：明确的触发时机
• 反馈机制：处理进度 + 结果展示
```

---

## 2. 数据资产分类

### 2.1 多模态数据源

```
100~500 TB 数据资产
    │
    ├── 📄 文档类 (Document)
    │   ├── PDF (复杂版面、扫描件、表格)
    │   ├── Word (.doc, .docx)
    │   ├── PowerPoint (.ppt, .pptx)
    │   └── 其他 (Markdown, HTML, TXT, Email)
    │
    ├── 📊 结构化数据 (Structured)
    │   ├── Excel (.xls, .xlsx)
    │   └── CSV / JSON
    │
    ├── 🖼️ 图像类 (Image)
    │   ├── 照片 (JPG, PNG)
    │   ├── 截图 / 扫描件
    │   ├── 漫画 / 插图
    │   └── 图表 / 信息图
    │
    └── 🎬 视频类 (Video)
        ├── 教学视频
        ├── 会议录制
        ├── 培训资料
        └── 产品演示
```

### 2.2 处理能力映射

| 数据类型 | 需要的核心能力 | UI 场景 |
|:---------|:---------------|:--------|
| PDF (文本) | 文本提取、分块 | 基础解析 |
| PDF (扫描) | OCR、版面分析 | 扫描件识别 |
| PDF (表格) | 表格检测、结构化 | 表格提取 |
| Word/PPT | 格式转换、嵌入图像处理 | Office 解析 |
| Excel | 单元格提取、关系识别 | 表格理解 |
| 图像 | VLM 描述、OCR | 图像理解 |
| 漫画 | 分格检测、气泡 OCR | 漫画识别 |
| 视频 | 关键帧提取、语音转文字、字幕 | 视频理解 |

---

## 3. 能力分类体系

### 3.1 能力四象限

```
                    场景复杂度
                        ↑
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    │  ③ 专业能力        │  ④ 高级能力        │
    │  (Pro)            │  (Advanced)       │
    │                   │                   │
    │  • 漫画识别        │  • GraphRAG       │
    │  • 视频理解        │  • RAPTOR        │
    │  • 复杂表格        │  • 多模态融合     │
技术 │                   │                   │
深度 ├───────────────────┼───────────────────┤
    │                   │                   │
    │  ① 基础能力        │  ② 增强能力        │
    │  (Basic)          │  (Enhanced)       │
    │                   │                   │
    │  • 文本提取        │  • 智能分块       │
    │  • 基础 OCR        │  • 表格识别       │
    │  • 文档分块        │  • 图像描述       │
    │                   │                   │
    └───────────────────┴───────────────────┘
```

### 3.2 能力注册表 (Capability Registry)

```yaml
# core/capabilities/registry.yaml (概念设计)

capabilities:
  # ═══════════════════════════════════════════════════
  # 基础能力 (Basic) - 默认启用
  # ═══════════════════════════════════════════════════
  text_extraction:
    id: "basic.text_extraction"
    name: "文本提取"
    category: "basic"
    description: "从 PDF/Word/PPT 中提取纯文本"
    icon: "document-text"
    default_enabled: true
    configurable: false
    supported_formats: [pdf, docx, pptx, txt, md, html]

  basic_chunking:
    id: "basic.chunking"
    name: "文档分块"
    category: "basic"
    description: "将长文档切分为检索单元"
    icon: "scissors"
    default_enabled: true
    configurable: true
    config_schema:
      chunk_size: { type: integer, min: 128, max: 2048, default: 512 }
      overlap: { type: integer, min: 0, max: 200, default: 50 }

  # ═══════════════════════════════════════════════════
  # 增强能力 (Enhanced) - 可选启用
  # ═══════════════════════════════════════════════════
  table_recognition:
    id: "enhanced.table_recognition"
    name: "表格识别"
    category: "enhanced"
    description: "识别文档中的表格并结构化为 Markdown/CSV"
    icon: "table"
    default_enabled: false
    configurable: true
    requires_gpu: true
    models:
      - id: "table_transformer"
        name: "TableTransformer"
        speed: "medium"
        accuracy: "high"
      - id: "pp_structure"
        name: "PP-Structure"
        speed: "fast"
        accuracy: "medium"
    config_schema:
      model: { type: enum, values: [table_transformer, pp_structure] }
      export_format: { type: enum, values: [markdown, csv, json] }

  image_understanding:
    id: "enhanced.image_understanding"
    name: "图像理解"
    category: "enhanced"
    description: "为图像生成语义描述，支持图表/照片/插图"
    icon: "image"
    default_enabled: false
    requires: ["vlm_provider"]
    config_schema:
      vlm_provider: { type: enum, values: [qwen-vl, gpt-4v, deepseek-vl] }
      detail_level: { type: enum, values: [brief, detailed, comprehensive] }

  ocr_enhanced:
    id: "enhanced.ocr"
    name: "高级 OCR"
    category: "enhanced"
    description: "扫描件/图片文字识别，支持多语言"
    icon: "scan"
    default_enabled: false
    requires_gpu: true
    config_schema:
      engine: { type: enum, values: [paddleocr, easyocr, tesseract] }
      languages: { type: array, items: string, default: [zh, en] }

  semantic_chunking:
    id: "enhanced.semantic_chunking"
    name: "语义分块"
    category: "enhanced"
    description: "基于语义边界智能切分文档"
    icon: "sparkles"
    default_enabled: false
    requires: ["embedding_provider"]
    config_schema:
      threshold: { type: float, min: 0.5, max: 0.95, default: 0.72 }

  # ═══════════════════════════════════════════════════
  # 专业能力 (Pro) - 特定场景
  # ═══════════════════════════════════════════════════
  comic_recognition:
    id: "pro.comic_recognition"
    name: "漫画识别"
    category: "pro"
    description: "漫画分格检测、对话气泡 OCR、场景描述"
    icon: "chat-bubble"
    default_enabled: false
    requires_gpu: true
    config_schema:
      panel_detection: { type: boolean, default: true }
      bubble_ocr: { type: boolean, default: true }
      scene_description: { type: boolean, default: false }

  video_understanding:
    id: "pro.video_understanding"
    name: "视频理解"
    category: "pro"
    description: "视频关键帧提取、语音转文字、内容摘要"
    icon: "video"
    default_enabled: false
    requires_gpu: true
    requires: ["whisper_model", "vlm_provider"]
    config_schema:
      keyframe_interval: { type: integer, min: 1, max: 60, default: 10 }
      transcription: { type: boolean, default: true }
      summarize: { type: boolean, default: false }

  excel_analysis:
    id: "pro.excel_analysis"
    name: "Excel 智能分析"
    category: "pro"
    description: "Excel 多 Sheet 解析、公式理解、数据关系识别"
    icon: "spreadsheet"
    default_enabled: false
    config_schema:
      parse_formulas: { type: boolean, default: false }
      detect_relations: { type: boolean, default: false }

  # ═══════════════════════════════════════════════════
  # 高级能力 (Advanced) - 知识增强
  # ═══════════════════════════════════════════════════
  raptor:
    id: "advanced.raptor"
    name: "RAPTOR 层级摘要"
    category: "advanced"
    description: "递归摘要聚类，构建多层知识树"
    icon: "tree"
    default_enabled: false
    requires: ["llm_provider", "embedding_provider"]
    config_schema:
      max_clusters: { type: integer, min: 8, max: 128, default: 64 }
      levels: { type: integer, min: 1, max: 5, default: 3 }
      scope: { type: enum, values: [whole_kb, per_document] }

  graphrag:
    id: "advanced.graphrag"
    name: "知识图谱"
    category: "advanced"
    description: "实体关系抽取，社区检测，图谱问答"
    icon: "network"
    default_enabled: false
    requires: ["llm_provider"]
    config_schema:
      entity_types: { type: array, items: string }
      community_detection: { type: boolean, default: true }
      community_summary: { type: boolean, default: false }

  multimodal_rag:
    id: "advanced.multimodal_rag"
    name: "多模态融合检索"
    category: "advanced"
    description: "文本+图像+表格联合检索"
    icon: "layers"
    default_enabled: false
    requires: ["vlm_provider", "embedding_provider"]
```

---

## 4. 知识库配置模型

### 4.1 KB 配置结构

```typescript
// 知识库配置 (前端可编辑)
interface KnowledgeBaseConfig {
  // 基础信息
  id: string;
  name: string;
  description: string;
  channel_id: string;

  // 能力配置 (显化)
  capabilities: {
    // 基础能力 (默认启用)
    basic: {
      text_extraction: true;
      chunking: {
        chunk_size: 512;
        overlap: 50;
      };
    };

    // 增强能力 (可选)
    enhanced: {
      table_recognition: {
        enabled: true;
        model: "table_transformer";
        export_format: "markdown";
      };
      image_understanding: {
        enabled: true;
        vlm_provider: "qwen-vl";
        detail_level: "detailed";
      };
      ocr: {
        enabled: false;  // 未启用, UI 显示为灰色
      };
    };

    // 专业能力 (场景化)
    pro: {
      comic_recognition: {
        enabled: false;
      };
      video_understanding: {
        enabled: true;
        keyframe_interval: 10;
        transcription: true;
      };
    };

    // 高级能力 (知识增强)
    advanced: {
      raptor: {
        enabled: false;
      };
      graphrag: {
        enabled: true;
        entity_types: ["person", "organization", "event"];
        community_detection: true;
      };
    };
  };

  // 检索配置
  retrieval: {
    top_k: 5;
    rerank_enabled: true;
    web_search_enabled: false;
  };
}
```

### 4.2 UI 能力卡片设计

```
┌─────────────────────────────────────────────────────────────────┐
│  知识库配置: 法律文书库                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📦 基础能力 (默认启用)                                          │
│  ┌────────────────┐ ┌────────────────┐                          │
│  │ ✅ 文本提取    │ │ ✅ 文档分块    │                          │
│  │ 自动启用       │ │ 512 字符/块    │ ← 可点击配置              │
│  └────────────────┘ └────────────────┘                          │
│                                                                  │
│  ⚡ 增强能力                                                     │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐       │
│  │ ✅ 表格识别    │ │ ⬜ 图像理解    │ │ ⬜ 高级 OCR    │       │
│  │ TableTransfmr │ │ 点击启用       │ │ 需要 GPU       │       │
│  │ → Markdown    │ │                 │ │                │       │
│  └────────────────┘ └────────────────┘ └────────────────┘       │
│                                                                  │
│  🎯 专业能力                                                     │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐       │
│  │ ⬜ 漫画识别    │ │ ⬜ 视频理解    │ │ ⬜ Excel 分析  │       │
│  │ 适用于漫画资源│ │ 需要 Whisper  │ │ 多 Sheet 解析  │       │
│  └────────────────┘ └────────────────┘ └────────────────┘       │
│                                                                  │
│  🧠 高级能力                                                     │
│  ┌────────────────┐ ┌────────────────┐                          │
│  │ ⬜ RAPTOR     │ │ ✅ 知识图谱    │                          │
│  │ 层级摘要树    │ │ 实体: 人/组织  │                          │
│  │ 需要 LLM     │ │ 社区检测: 开   │ ← 详细配置               │
│  └────────────────┘ └────────────────┘                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ [保存配置]  [重置为默认]  [查看能力详情]                     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Core 模块与能力映射

### 5.1 模块-能力关系

```
core/
├── ingestion/                          # 摄取管道
│   ├── nodes/
│   │   ├── parser/
│   │   │   ├── cpu_parser.py          → basic.text_extraction (PDF/Word/PPT/TXT)
│   │   │   └── gpu_parser.py          → enhanced.ocr, pro.comic_recognition
│   │   ├── chunker.py                 → basic.chunking, enhanced.semantic_chunking
│   │   ├── embedder.py                → (内部支撑, 非用户直接配置)
│   │   ├── indexer.py                 → (内部支撑)
│   │   ├── image_captioner.py         → enhanced.image_understanding
│   │   └── table_extractor.py         → enhanced.table_recognition (待新建)
│   │
│   └── processors/                     # 新建: 专业处理器
│       ├── video_processor.py         → pro.video_understanding
│       ├── excel_processor.py         → pro.excel_analysis
│       └── comic_processor.py         → pro.comic_recognition
│
├── algorithms/
│   ├── raptor_deep.py                 → advanced.raptor
│   ├── raptor_light.py                → advanced.raptor (简化版)
│   ├── graphrag_deep.py               → advanced.graphrag
│   └── mindmap_light.py               → (内部)
│
├── retrieval/                          # 检索管道
│   └── nodes/
│       ├── retriever.py               → (内部, 由 retrieval config 控制)
│       ├── reranker.py                → retrieval.rerank_enabled
│       └── generator.py               → (内部)
│
└── capabilities/                       # 新建: 能力层
    ├── registry.py                    ← 能力注册表
    ├── loader.py                      ← 按需加载能力模块
    ├── validator.py                   ← 配置校验
    └── manifest.yaml                  ← 能力清单 (静态定义)
```

### 5.2 能力加载器设计

```python
# core/capabilities/loader.py

from typing import Any
from core.capabilities.registry import CapabilityRegistry


class CapabilityLoader:
    """
    按需加载能力模块

    设计原则:
    1. 懒加载: 只有启用的能力才加载模型
    2. 显化: 能力状态可查询
    3. 热更新: 配置变更无需重启
    """

    def __init__(self):
        self.registry = CapabilityRegistry()
        self._loaded: dict[str, Any] = {}
        self._status: dict[str, str] = {}  # ready/loading/error/disabled

    async def prepare_for_kb(self, kb_config: dict) -> dict[str, str]:
        """
        根据 KB 配置准备所需能力

        Returns:
            capability_id -> status 映射
        """
        capabilities = kb_config.get("capabilities", {})
        status = {}

        for category in ["basic", "enhanced", "pro", "advanced"]:
            cat_config = capabilities.get(category, {})
            for cap_id, cap_config in cat_config.items():
                full_id = f"{category}.{cap_id}"

                if isinstance(cap_config, dict) and cap_config.get("enabled"):
                    status[full_id] = await self._load_capability(full_id, cap_config)
                elif cap_config is True:
                    status[full_id] = await self._load_capability(full_id, {})
                else:
                    status[full_id] = "disabled"
                    self._status[full_id] = "disabled"

        return status

    async def _load_capability(self, cap_id: str, config: dict) -> str:
        """加载单个能力"""
        if cap_id in self._loaded:
            return "ready"

        self._status[cap_id] = "loading"

        try:
            # 检查依赖
            cap_def = self.registry.get(cap_id)
            for dep in cap_def.get("requires", []):
                if not self._check_dependency(dep, config):
                    self._status[cap_id] = f"missing_dependency:{dep}"
                    return f"error:missing_{dep}"

            # 加载模块
            module = await self._import_capability_module(cap_id)
            instance = module.create(config)

            self._loaded[cap_id] = instance
            self._status[cap_id] = "ready"
            return "ready"

        except Exception as e:
            self._status[cap_id] = f"error:{str(e)}"
            return f"error:{str(e)}"

    def get_status(self) -> dict[str, str]:
        """获取所有能力状态 (用于 UI 展示)"""
        return dict(self._status)

    def get_capability(self, cap_id: str) -> Any:
        """获取已加载的能力实例"""
        if cap_id not in self._loaded:
            raise RuntimeError(f"Capability {cap_id} not loaded")
        return self._loaded[cap_id]
```

---

## 6. 后续规划

### 6.1 Phase 1: 能力框架 (1 周)

| 任务 | 说明 |
|:-----|:-----|
| 创建 `core/capabilities/` 模块 | 能力注册、加载、状态管理 |
| 定义能力 Manifest | YAML 格式能力清单 |
| KB 配置扩展 | 在 `kb_config` 中加入 capabilities 字段 |

### 6.2 Phase 2: 能力实现 (2 周)

| 能力 | 实现 |
|:-----|:-----|
| 表格识别 | `table_extractor.py` + TableTransformer |
| 视频理解 | `video_processor.py` + Whisper + 帧抽取 |
| Excel 解析 | `excel_processor.py` + openpyxl |
| 漫画识别 | `comic_processor.py` + 分格检测 |

### 6.3 Phase 3: UI 集成 (1 周)

| 组件 | 说明 |
|:-----|:-----|
| 能力卡片组件 | 显示能力状态、启用/禁用 |
| 配置面板 | 能力参数编辑 |
| 状态指示器 | ready/loading/error 状态 |
| 配置变更 API | 热更新能力配置 |

### 6.4 Phase 4: 大规模处理 (持续)

- 将处理管道与能力框架对接
- 分布式任务调度
- 质量监控仪表盘

---

## 7. 设计检查清单

| 检查项 | 状态 | 说明 |
|:-------|:----:|:-----|
| 能力是否可见 | ⬜ | UI 能力卡片展示 |
| 能力是否可配置 | ⬜ | KB 级别独立配置 |
| 能力是否场景化 | ⬜ | 明确的使用场景描述 |
| 能力是否即用 | ⬜ | 配置变更无需重启 |
| 能力是否显化 | ⬜ | 分类清晰、状态可见 |
| 避免沉默 | ⬜ | 无隐藏/无反馈的能力 |

---

*文档版本: v1.0*
*产品视角: 能力产品化*
*技术视角: 模块化 + 可配置*
