# OmniRAG 垂直领域解读能力增强方案

> **版本**: v2.0 | **日期**: 2025-12-14
> **目标**: 为 core 接入 100TB+ 数据的垂直化深度解读与叙事能力
> **设计原则**: 最大性价比 · 多云弹性 · 灵活配置 · 随时扩展

---

## 📐 设计原则

### 原则 1: 最大性价比 - 避免盲目使用 GPU 算力

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COST-EFFECTIVE COMPUTE STRATEGY                         │
│                         "能不用 GPU 就不用 GPU"                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   决策树: 任务 → 评估 → 选择最优路径                                          │
│                                                                              │
│   ┌─────────────┐                                                           │
│   │   新任务    │                                                           │
│   └──────┬──────┘                                                           │
│          ▼                                                                   │
│   ┌─────────────────┐    Yes    ┌─────────────────────────┐                │
│   │ 是否有缓存结果？ │─────────→│ 直接返回缓存 (成本: $0) │                │
│   └────────┬────────┘          └─────────────────────────┘                │
│            │ No                                                              │
│            ▼                                                                 │
│   ┌─────────────────┐    Yes    ┌─────────────────────────┐                │
│   │ CPU 能否完成？   │─────────→│ 使用 CPU (成本: $0.001) │                │
│   └────────┬────────┘          └─────────────────────────┘                │
│            │ No                                                              │
│            ▼                                                                 │
│   ┌─────────────────┐    Yes    ┌─────────────────────────┐                │
│   │ 云API更便宜？    │─────────→│ 调用云API (成本: $0.01) │                │
│   └────────┬────────┘          └─────────────────────────┘                │
│            │ No                                                              │
│            ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                 使用本地/云端 GPU (成本: $0.10+)                      │  │
│   │   优先级: 本地GPU → Spot实例 → 按需实例 → 高端GPU                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 原则 2: 多云算力 Provider 可插拔架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-CLOUD COMPUTE PROVIDER ARCHITECTURE                 │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      ComputeProviderRegistry                         │   │
│   │   统一接口 · 动态注册 · 热切换 · 故障转移                             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│            ┌─────────────────────────┼─────────────────────────┐            │
│            ▼                         ▼                         ▼            │
│   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐          │
│   │  阿里云百炼      │   │   火山方舟       │   │  Microsoft Azure │          │
│   │  (DashScope)    │   │   (Volcengine)   │   │  (Azure OpenAI)  │          │
│   ├─────────────────┤   ├─────────────────┤   ├─────────────────┤          │
│   │ • Qwen-VL       │   │ • Doubao-Vision │   │ • GPT-4V        │          │
│   │ • Qwen-Max      │   │ • Doubao-Pro    │   │ • GPT-4o        │          │
│   │ • BGE-M3        │   │ • BGE-Large     │   │ • Ada-002       │          │
│   │ • PAI-EAS GPU   │   │ • MaaS GPU      │   │ • Azure ML GPU  │          │
│   └─────────────────┘   └─────────────────┘   └─────────────────┘          │
│            │                         │                         │            │
│            └─────────────────────────┼─────────────────────────┘            │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        Unified API Interface                         │   │
│   │   chat() | embed() | vision() | gpu_compute() | batch_process()     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 核心价值主张

RAG 系统的核心价值不在于"通用问答"，而在于**垂直领域的深度解读能力**：

| 能力层级 | 通用 RAG | 垂直增强 RAG |
|:---------|:---------|:-------------|
| 文本处理 | 分块检索 | 领域语义理解 |
| 图像处理 | OCR + 描述 | 画风/叙事/人物解析 |
| 知识建模 | 实体关系 | 领域本体图谱 |
| 输出形式 | 问答 | 结构化解读报告 |

---

## 📋 能力增强 Prompt

### Prompt 1: 垂直领域元能力定义器

```yaml
# 系统指令 (System Prompt)
# 用于定义新垂直领域的解读框架

你是 OmniRAG 垂直领域能力设计师。你的任务是为特定垂直领域定义完整的解读能力框架。

## 输入
- 领域名称: {domain_name}
- 领域描述: {domain_description}
- 示例文档/图像: {sample_artifacts}

## 输出：能力定义清单 (JSON Schema)
{
  "domain_id": "string",
  "domain_name": "string",
  "ontology": {
    "entities": ["实体类型列表，如：人物、符号、卦象、天象..."],
    "relations": ["关系类型列表，如：师徒、克制、生成..."],
    "attributes": ["属性类型列表，如：属性、年代、派别..."]
  },
  "visual_schema": {
    "art_styles": ["画风分类，如：工笔、水墨、漫画..."],
    "visual_elements": ["视觉元素，如：对话气泡、分格、装饰纹..."],
    "composition_patterns": ["构图模式，如：四联叙事、对话场景..."]
  },
  "narrative_schema": {
    "discourse_types": ["话语类型，如：讲解、对话、旁白..."],
    "knowledge_density": "low|medium|high",
    "temporal_structure": "linear|cyclical|branching"
  },
  "interpretation_rules": [
    {
      "trigger": "触发条件描述",
      "action": "解读动作描述",
      "output_format": "输出格式"
    }
  ],
  "gpu_requirements": {
    "min_vram_gb": 8,
    "recommended_vram_gb": 24,
    "reason": "VLM 多格图像推理需要"
  }
}
```

---

### Prompt 2: 多模态垂直解读器 (核心能力)

```yaml
# 系统指令 (System Prompt)
# 执行垂直领域的多模态深度解读

你是 OmniRAG 垂直领域解读引擎。你的任务是对特定领域的文档/图像进行深度语义解读。

## 领域配置
- 领域 ID: {domain_id}
- 领域本体: {ontology}
- 解读规则: {interpretation_rules}

## 输入
- 内容类型: {content_type}  # image | pdf_page | text
- 原始内容: {raw_content}   # base64 图像 | 文本
- 上下文: {context}         # 前后页/关联内容

## 解读流程

### Phase 1: 视觉/文本分解 (Decomposition)
对于图像:
1. 检测布局区域: [标题区, 正文区, 对话气泡, 人物区, 装饰区]
2. 识别视觉元素: [人物姿态, 表情, 服饰, 背景元素, 符号]
3. OCR 文字提取: [按区域分组]

对于文本:
1. 分段落/分句
2. 识别专业术语
3. 标注知识点

### Phase 2: 语义理解 (Semantic Understanding)
1. 领域实体识别: 根据 {ontology.entities} 抽取实体
2. 关系抽取: 根据 {ontology.relations} 建立关联
3. 属性填充: 根据 {ontology.attributes} 补充属性
4. 画风/风格判断: 根据 {visual_schema} 分类

### Phase 3: 叙事重构 (Narrative Reconstruction)
1. 确定叙事类型: {narrative_schema.discourse_types}
2. 重建叙事逻辑链:
   - 背景设定 → 核心观点 → 论证/展开 → 结论/启示
3. 生成结构化摘要

### Phase 4: 知识增强 (Knowledge Augmentation)
1. 链接到已有知识图谱
2. 补充领域背景知识
3. 标注置信度与来源

## 输出格式 (JSON)
{
  "content_id": "string",
  "domain": "{domain_id}",
  "decomposition": {
    "regions": [...],
    "ocr_texts": {...},
    "visual_elements": [...]
  },
  "semantic_understanding": {
    "entities": [
      {"name": "...", "type": "...", "attributes": {...}, "confidence": 0.95}
    ],
    "relations": [
      {"src": "...", "tgt": "...", "type": "...", "confidence": 0.90}
    ]
  },
  "narrative": {
    "type": "讲解/对话/...",
    "summary": "一句话摘要",
    "detailed_interpretation": "完整解读文本",
    "knowledge_points": ["知识点1", "知识点2"],
    "art_style": "画风描述",
    "emotional_tone": "情感基调"
  },
  "metadata": {
    "processing_time_ms": 1234,
    "gpu_used": true,
    "model_versions": {...}
  }
}
```

---

### Prompt 3: 示例 - 命理/玄学领域配置

```json
{
  "domain_id": "metaphysics_chinese",
  "domain_name": "中国传统命理玄学",
  "ontology": {
    "entities": [
      "天干", "地支", "五行", "八卦", "神煞", 
      "人物", "天象", "历法周期", "命格", "运势"
    ],
    "relations": [
      "生", "克", "刑", "冲", "合", "害",
      "师承", "印证", "推演", "应验"
    ],
    "attributes": [
      "阴阳属性", "五行属性", "旺衰状态", 
      "时间周期", "吉凶判断", "年代归属"
    ]
  },
  "visual_schema": {
    "art_styles": [
      "传统工笔", "白描线条", "水墨写意", 
      "现代漫画简化", "古籍插图风"
    ],
    "visual_elements": [
      "道士/术士形象", "八卦图", "天干地支表",
      "对话气泡", "批注框", "卷轴/书籍道具"
    ],
    "composition_patterns": [
      "讲解场景(讲者+听者)", 
      "示例演算场景",
      "历史典故场景",
      "概念图解场景"
    ]
  },
  "narrative_schema": {
    "discourse_types": [
      "理论讲解", "案例分析", "口诀传承",
      "历史典故", "师徒对话", "实操演示"
    ],
    "knowledge_density": "high",
    "temporal_structure": "cyclical"
  },
  "interpretation_rules": [
    {
      "trigger": "检测到八卦/天干地支符号",
      "action": "触发命理术语知识库检索，补充专业解释",
      "output_format": "术语+解释+出处"
    },
    {
      "trigger": "检测到人物对话场景",
      "action": "识别讲者/听者角色，提取对话核心观点",
      "output_format": "角色+观点+情感"
    },
    {
      "trigger": "检测到数字/周期描述",
      "action": "映射到命理周期体系(甲子/大运/流年等)",
      "output_format": "数字+周期类型+含义"
    }
  ],
  "gpu_requirements": {
    "min_vram_gb": 8,
    "recommended_vram_gb": 24,
    "reason": "VLM 图像理解 + 领域 Fine-tuned 模型推理"
  }
}
```

---

### Prompt 4: 示例 - 四联漫画领域配置

```json
{
  "domain_id": "comic_four_panel",
  "domain_name": "四联漫画叙事解读",
  "ontology": {
    "entities": [
      "角色", "场景", "道具", "情绪符号",
      "音效文字", "旁白", "时间标记"
    ],
    "relations": [
      "对话", "动作", "因果", "转折",
      "时间顺序", "空间位置"
    ],
    "attributes": [
      "角色性格", "表情状态", "动作类型",
      "场景氛围", "叙事功能(起承转合)"
    ]
  },
  "visual_schema": {
    "art_styles": [
      "日式漫画", "美式漫画", "欧式漫画",
      "简笔条漫", "写实风", "Q版风"
    ],
    "visual_elements": [
      "分格边框", "对话气泡(椭圆/云朵/锯齿/方框)",
      "运动线", "集中线", "汗滴", "星星/心形",
      "拟声词", "背景效果线"
    ],
    "composition_patterns": [
      "起-承-转-合四段式",
      "对比反差式",
      "时间推进式",
      "空间切换式"
    ]
  },
  "narrative_schema": {
    "discourse_types": [
      "搞笑/吐槽", "讽刺/隐喻", "日常/治愈",
      "悬疑/反转", "科普/教育", "情感/共鸣"
    ],
    "knowledge_density": "medium",
    "temporal_structure": "linear"
  },
  "interpretation_rules": [
    {
      "trigger": "四格漫画布局",
      "action": "按起-承-转-合结构解读叙事逻辑",
      "output_format": "第N格功能 + 内容描述 + 叙事作用"
    },
    {
      "trigger": "对话气泡",
      "action": "识别说话者、气泡类型(普通/心理/喊叫)、对话内容",
      "output_format": "说话者 + 语气 + 台词 + 情感"
    },
    {
      "trigger": "表情/动作夸张表现",
      "action": "识别情绪类型和强度",
      "output_format": "情绪类型 + 强度等级(1-5) + 视觉表现手法"
    }
  ],
  "gpu_requirements": {
    "min_vram_gb": 16,
    "recommended_vram_gb": 48,
    "reason": "漫画分格检测 + 多角色追踪 + 叙事理解需要大模型"
  }
}
```

---

## 🏗️ Core 能力扩展架构

### 新增能力模块

```
core/
├── domains/                          # 新增: 垂直领域模块
│   ├── __init__.py
│   ├── registry.py                   # 领域注册器
│   ├── base_interpreter.py           # 基础解读器接口
│   ├── metaphysics/                  # 命理玄学领域
│   │   ├── __init__.py
│   │   ├── ontology.yaml             # 领域本体定义
│   │   ├── interpreter.py            # 领域解读器
│   │   └── knowledge_base/           # 领域知识库
│   ├── comic/                        # 漫画领域
│   │   ├── __init__.py
│   │   ├── ontology.yaml
│   │   ├── interpreter.py
│   │   └── panel_detector.py         # 分格检测
│   └── custom/                       # 自定义领域模板
│       └── template.yaml
│
├── capabilities/
│   └── manifest.yaml                 # 扩展: 添加垂直领域能力
│
├── ingestion/
│   └── processors/
│       └── domain_aware_processor.py # 新增: 领域感知处理器
│
└── retrieval/
    └── domain_enhanced_retriever.py  # 新增: 领域增强检索器
```

### Manifest 扩展: 垂直领域能力卡片

```yaml
# 添加到 manifest.yaml

  # ─────────────────────────────────────────────────────────────────────────────
  # 垂直领域解读 (Vertical Domain Interpretation)
  # ─────────────────────────────────────────────────────────────────────────────
  vertical_domain:
    id: "advanced.vertical_domain"
    category: "advanced"

    name: "垂直领域解读"
    name_en: "Vertical Domain Interpretation"
    description: "为特定领域配置深度语义理解和叙事重构能力"
    description_en: "Configure deep semantic understanding and narrative reconstruction for specific domains"
    icon: "academic-cap"

    use_case: "命理分析、漫画解读、法律条文、医学影像等垂直场景"

    default_enabled: false
    user_configurable: true

    # ⚠️ GPU 需求标注
    requires_gpu: true
    gpu_memory_mb: 24576  # 24GB VRAM minimum
    gpu_recommended_mb: 49152  # 48GB for optimal performance

    requires:
      - vlm_provider
      - llm_provider
      - embedding

    implementation:
      module: "core.domains.registry"
      class: "DomainInterpreterRegistry"

    config_schema:
      type: object
      properties:
        domain_id:
          type: string
          title: "领域选择"
          description: "选择预置领域或自定义"
          enum: ["metaphysics_chinese", "comic_four_panel", "legal_chinese", "medical_imaging", "custom"]
          enum_labels:
            metaphysics_chinese: "中国传统命理"
            comic_four_panel: "四联漫画"
            legal_chinese: "中国法律法规"
            medical_imaging: "医学影像"
            custom: "自定义领域"
          default: "custom"
          ui_component: "select"

        interpretation_depth:
          type: string
          title: "解读深度"
          description: "解读的详细程度"
          enum: ["surface", "standard", "deep", "exhaustive"]
          enum_labels:
            surface: "表层 (快速)"
            standard: "标准"
            deep: "深度"
            exhaustive: "穷尽式 (最慢)"
          default: "standard"
          ui_component: "select"

        narrative_reconstruction:
          type: boolean
          title: "叙事重构"
          description: "生成结构化叙事摘要"
          default: true
          ui_component: "switch"

        knowledge_linking:
          type: boolean
          title: "知识链接"
          description: "链接到领域知识图谱"
          default: true
          ui_component: "switch"

        custom_ontology_url:
          type: string
          title: "自定义本体 URL"
          description: "YAML/JSON 格式的领域本体定义"
          default: ""
          ui_component: "text"
          ui_show_if:
            field: "domain_id"
            value: "custom"
```

---

## ⚡ GPU 算力基础设施架构

### 核心设计原则

| 原则 | 描述 | 实现方式 |
|:-----|:-----|:---------|
| **最大性价比** | 避免盲目使用GPU，优先低成本方案 | 智能路由决策树 + 成本评估器 |
| **多云弹性** | 接入阿里云百炼、火山方舟、Azure | 统一 Provider 抽象层 |
| **灵活配置** | 运行时动态切换，无需重启 | DB 驱动配置 + 热加载 |
| **随时扩展** | 新增 Provider 只需实现接口 | 插件化注册机制 |

### 算力分层架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GPU COMPUTE TIER ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   TIER 0: CPU-Only (成本最低 ⭐首选)                                         │
│   ├── 纯文本处理、轻量分块                                                   │
│   ├── 缓存命中场景                                                           │
│   └── 成本: ~$0/请求                                                         │
│                                                                              │
│   TIER 1: Cloud API (按需付费 ⭐推荐)                                        │
│   ├── VLM 图像理解 (Qwen-VL API, GPT-4V API)                                 │
│   ├── LLM 文本生成                                                           │
│   ├── Embedding 生成                                                         │
│   └── 成本: ~$0.001-0.10/请求                                                │
│                                                                              │
│   TIER 2: Spot/抢占式实例 (批量任务)                                         │
│   ├── 大规模 Embedding 生成                                                  │
│   ├── 批量文档处理                                                           │
│   ├── 非实时 GraphRAG 构建                                                   │
│   └── 成本: 按需实例的 30%-70%                                               │
│                                                                              │
│   TIER 3: 按需 GPU 实例 (实时需求)                                           │
│   ├── 本地模型推理                                                           │
│   ├── Fine-tuned 领域模型                                                    │
│   ├── 实时流式处理                                                           │
│   └── 成本: ~$0.50-5.00/小时                                                 │
│                                                                              │
│   TIER 4: 高端 GPU 集群 (大规模训练/推理)                                    │
│   ├── 模型微调                                                               │
│   ├── 超大规模并行处理                                                       │
│   └── 成本: ~$10-50/小时                                                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔌 多云算力 Provider 完整实现

### Provider 配置 Schema

```yaml
# core/compute/providers.yaml
# 多云算力 Provider 统一配置

version: "1.0"
last_updated: "2025-12-14"

# ═══════════════════════════════════════════════════════════════════════════════
# 全局策略配置
# ═══════════════════════════════════════════════════════════════════════════════
global_strategy:
  # 成本优化开关
  cost_optimization: true
  
  # 默认路由策略: cost_first | performance_first | balanced
  routing_strategy: "cost_first"
  
  # 故障转移启用
  failover_enabled: true
  
  # 最大重试次数
  max_retries: 3
  
  # 缓存配置
  cache:
    enabled: true
    ttl_seconds: 3600
    max_size_mb: 1024

# ═══════════════════════════════════════════════════════════════════════════════
# Provider 定义
# ═══════════════════════════════════════════════════════════════════════════════
providers:

  # ─────────────────────────────────────────────────────────────────────────────
  # 阿里云百炼 (DashScope)
  # ─────────────────────────────────────────────────────────────────────────────
  dashscope:
    id: "dashscope"
    name: "阿里云百炼"
    name_en: "Alibaba DashScope"
    category: "domestic"
    enabled: true
    priority: 1  # 国内首选
    
    # 认证配置
    auth:
      type: "api_key"
      env_vars:
        - "DASHSCOPE_API_KEY"
      config_path: "providers.dashscope.api_key"
    
    # 端点配置
    endpoints:
      chat: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
      embedding: "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
      vision: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
      batch: "https://dashscope.aliyuncs.com/api/v1/tasks"
    
    # 模型配置
    models:
      llm:
        - id: "qwen-max"
          name: "Qwen-Max"
          context_length: 32768
          cost_per_1k_tokens: 0.02
          recommended_for: ["complex_reasoning", "long_context"]
        
        - id: "qwen-plus"
          name: "Qwen-Plus"
          context_length: 131072
          cost_per_1k_tokens: 0.004
          recommended_for: ["general", "cost_sensitive"]
        
        - id: "qwen-turbo"
          name: "Qwen-Turbo"
          context_length: 131072
          cost_per_1k_tokens: 0.002
          recommended_for: ["high_throughput", "simple_tasks"]
      
      vlm:
        - id: "qwen-vl-max"
          name: "Qwen-VL-Max"
          cost_per_image: 0.01
          max_images: 10
          recommended_for: ["document_understanding", "chart_analysis"]
        
        - id: "qwen-vl-plus"
          name: "Qwen-VL-Plus"
          cost_per_image: 0.004
          max_images: 10
          recommended_for: ["general_vision", "ocr"]
      
      embedding:
        - id: "text-embedding-v3"
          name: "Text Embedding V3"
          dimension: 1024
          cost_per_1k_tokens: 0.0007
          max_tokens: 8192
    
    # GPU 算力服务 (PAI-EAS)
    gpu_compute:
      enabled: true
      service: "pai-eas"
      regions: ["cn-hangzhou", "cn-shanghai", "cn-beijing"]
      instance_types:
        - type: "ecs.gn7i-c8g1.2xlarge"
          gpu: "A10"
          vram_gb: 24
          hourly_cost: 3.5
        - type: "ecs.gn7-c13g1.4xlarge"
          gpu: "V100"
          vram_gb: 32
          hourly_cost: 5.0
        - type: "ecs.gn7e-c16g1.4xlarge"
          gpu: "A100"
          vram_gb: 80
          hourly_cost: 15.0
      spot_discount: 0.3  # Spot 实例折扣

    # 限流配置
    rate_limits:
      requests_per_minute: 1000
      tokens_per_minute: 1000000
      concurrent_requests: 100
    
    # 健康检查
    health_check:
      endpoint: "https://dashscope.aliyuncs.com/compatible-mode/v1/models"
      interval_seconds: 60
      timeout_seconds: 10

  # ─────────────────────────────────────────────────────────────────────────────
  # 火山方舟 (Volcengine Ark)
  # ─────────────────────────────────────────────────────────────────────────────
  volcengine:
    id: "volcengine"
    name: "火山方舟"
    name_en: "Volcengine Ark"
    category: "domestic"
    enabled: true
    priority: 2
    
    auth:
      type: "api_key"
      env_vars:
        - "VOLCENGINE_API_KEY"
        - "VOLCENGINE_ENDPOINT_ID"  # 端点 ID
      config_path: "providers.volcengine.api_key"
    
    endpoints:
      chat: "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
      embedding: "https://ark.cn-beijing.volces.com/api/v3/embeddings"
      vision: "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
      batch: "https://ark.cn-beijing.volces.com/api/v3/batches"
    
    models:
      llm:
        - id: "doubao-pro-256k"
          name: "Doubao-Pro-256K"
          context_length: 262144
          cost_per_1k_tokens: 0.005
          endpoint_id_env: "VOLCENGINE_DOUBAO_PRO_ENDPOINT"
          recommended_for: ["long_context", "document_analysis"]
        
        - id: "doubao-lite-128k"
          name: "Doubao-Lite-128K"
          context_length: 131072
          cost_per_1k_tokens: 0.0008
          endpoint_id_env: "VOLCENGINE_DOUBAO_LITE_ENDPOINT"
          recommended_for: ["high_throughput", "cost_sensitive"]
      
      vlm:
        - id: "doubao-vision-pro"
          name: "Doubao-Vision-Pro"
          cost_per_image: 0.008
          max_images: 30
          endpoint_id_env: "VOLCENGINE_VISION_ENDPOINT"
          recommended_for: ["complex_vision", "multi_image"]
        
        - id: "doubao-vision-lite"
          name: "Doubao-Vision-Lite"
          cost_per_image: 0.003
          max_images: 10
          recommended_for: ["simple_ocr", "basic_understanding"]
      
      embedding:
        - id: "doubao-embedding"
          name: "Doubao Embedding"
          dimension: 2560
          cost_per_1k_tokens: 0.0005
          max_tokens: 4096
    
    gpu_compute:
      enabled: true
      service: "maas"
      regions: ["cn-beijing", "cn-shanghai"]
      instance_types:
        - type: "ml.gu7xne.xlarge"
          gpu: "A10"
          vram_gb: 24
          hourly_cost: 3.2
        - type: "ml.gu7xne.2xlarge"
          gpu: "A10x2"
          vram_gb: 48
          hourly_cost: 6.0
      spot_discount: 0.35

    rate_limits:
      requests_per_minute: 500
      tokens_per_minute: 500000
      concurrent_requests: 50
    
    health_check:
      endpoint: "https://ark.cn-beijing.volces.com/api/v3/models"
      interval_seconds: 60
      timeout_seconds: 10

  # ─────────────────────────────────────────────────────────────────────────────
  # Microsoft Azure OpenAI
  # ─────────────────────────────────────────────────────────────────────────────
  azure:
    id: "azure"
    name: "Azure OpenAI"
    name_en: "Microsoft Azure OpenAI"
    category: "foreign"
    enabled: true
    priority: 3
    
    auth:
      type: "api_key"
      env_vars:
        - "AZURE_OPENAI_API_KEY"
        - "AZURE_OPENAI_ENDPOINT"
        - "AZURE_OPENAI_API_VERSION"
      config_path: "providers.azure.api_key"
    
    endpoints:
      # Azure 使用自定义端点格式
      chat: "{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
      embedding: "{endpoint}/openai/deployments/{deployment}/embeddings?api-version={api_version}"
      vision: "{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    
    models:
      llm:
        - id: "gpt-4o"
          name: "GPT-4o"
          deployment_name_env: "AZURE_GPT4O_DEPLOYMENT"
          context_length: 128000
          cost_per_1k_tokens: 0.01
          recommended_for: ["complex_reasoning", "multimodal"]
        
        - id: "gpt-4o-mini"
          name: "GPT-4o-Mini"
          deployment_name_env: "AZURE_GPT4O_MINI_DEPLOYMENT"
          context_length: 128000
          cost_per_1k_tokens: 0.0015
          recommended_for: ["general", "cost_sensitive"]
        
        - id: "gpt-4-turbo"
          name: "GPT-4-Turbo"
          deployment_name_env: "AZURE_GPT4_TURBO_DEPLOYMENT"
          context_length: 128000
          cost_per_1k_tokens: 0.03
          recommended_for: ["high_quality", "complex_tasks"]
      
      vlm:
        - id: "gpt-4o-vision"
          name: "GPT-4o Vision"
          deployment_name_env: "AZURE_GPT4O_DEPLOYMENT"
          cost_per_image: 0.01
          max_images: 10
          recommended_for: ["document_analysis", "chart_understanding"]
      
      embedding:
        - id: "text-embedding-3-large"
          name: "Text Embedding 3 Large"
          deployment_name_env: "AZURE_EMBEDDING_LARGE_DEPLOYMENT"
          dimension: 3072
          cost_per_1k_tokens: 0.00013
          max_tokens: 8191
        
        - id: "text-embedding-3-small"
          name: "Text Embedding 3 Small"
          deployment_name_env: "AZURE_EMBEDDING_SMALL_DEPLOYMENT"
          dimension: 1536
          cost_per_1k_tokens: 0.00002
          max_tokens: 8191
    
    gpu_compute:
      enabled: true
      service: "azure-ml"
      regions: ["eastus", "westus2", "westeurope", "eastasia"]
      instance_types:
        - type: "Standard_NC24ads_A100_v4"
          gpu: "A100"
          vram_gb: 80
          hourly_cost: 3.67
        - type: "Standard_NC48ads_A100_v4"
          gpu: "A100x2"
          vram_gb: 160
          hourly_cost: 7.35
        - type: "Standard_ND96amsr_A100_v4"
          gpu: "A100x8"
          vram_gb: 640
          hourly_cost: 27.20
      spot_discount: 0.4

    rate_limits:
      requests_per_minute: 600
      tokens_per_minute: 150000
      concurrent_requests: 100
    
    health_check:
      endpoint: "{endpoint}/openai/models?api-version={api_version}"
      interval_seconds: 60
      timeout_seconds: 10

  # ─────────────────────────────────────────────────────────────────────────────
  # DeepSeek (高性价比选项)
  # ─────────────────────────────────────────────────────────────────────────────
  deepseek:
    id: "deepseek"
    name: "DeepSeek"
    name_en: "DeepSeek AI"
    category: "domestic"
    enabled: true
    priority: 4
    
    auth:
      type: "api_key"
      env_vars:
        - "DEEPSEEK_API_KEY"
      config_path: "providers.deepseek.api_key"
    
    endpoints:
      chat: "https://api.deepseek.com/v1/chat/completions"
      embedding: null  # DeepSeek 暂无 embedding API
      vision: "https://api.deepseek.com/v1/chat/completions"
    
    models:
      llm:
        - id: "deepseek-chat"
          name: "DeepSeek-V3"
          context_length: 65536
          cost_per_1k_tokens: 0.001  # 极具性价比
          recommended_for: ["general", "code", "cost_sensitive"]
        
        - id: "deepseek-reasoner"
          name: "DeepSeek-R1"
          context_length: 65536
          cost_per_1k_tokens: 0.004
          recommended_for: ["complex_reasoning", "math", "code"]
      
      vlm:
        - id: "deepseek-vl"
          name: "DeepSeek-VL"
          cost_per_image: 0.002
          max_images: 5
          recommended_for: ["basic_vision", "cost_sensitive"]

    rate_limits:
      requests_per_minute: 1000
      tokens_per_minute: 10000000
      concurrent_requests: 200

# ═══════════════════════════════════════════════════════════════════════════════
# 路由规则配置
# ═══════════════════════════════════════════════════════════════════════════════
routing_rules:
  
  # 按任务类型路由
  task_routing:
    - task_type: "simple_chat"
      preferred_providers: ["deepseek", "dashscope", "volcengine"]
      preferred_models: ["deepseek-chat", "qwen-turbo", "doubao-lite-128k"]
      max_cost_per_request: 0.01
    
    - task_type: "complex_reasoning"
      preferred_providers: ["deepseek", "dashscope", "azure"]
      preferred_models: ["deepseek-reasoner", "qwen-max", "gpt-4o"]
      max_cost_per_request: 0.10
    
    - task_type: "vision_understanding"
      preferred_providers: ["dashscope", "volcengine", "azure"]
      preferred_models: ["qwen-vl-max", "doubao-vision-pro", "gpt-4o-vision"]
      max_cost_per_request: 0.05
    
    - task_type: "embedding"
      preferred_providers: ["dashscope", "volcengine", "azure"]
      preferred_models: ["text-embedding-v3", "doubao-embedding", "text-embedding-3-small"]
      max_cost_per_request: 0.001
    
    - task_type: "batch_processing"
      preferred_providers: ["dashscope", "volcengine"]
      use_spot_instances: true
      max_cost_per_1k_items: 5.0
  
  # 按区域路由 (合规要求)
  region_routing:
    - region: "china"
      allowed_providers: ["dashscope", "volcengine", "deepseek"]
      reason: "数据合规，中国境内数据不出境"
    
    - region: "global"
      allowed_providers: ["azure", "dashscope", "volcengine", "deepseek"]
      reason: "全球访问，优先低延迟"
  
  # 故障转移链
  failover_chains:
    - primary: "dashscope"
      fallbacks: ["volcengine", "deepseek", "azure"]
    
    - primary: "volcengine"
      fallbacks: ["dashscope", "deepseek", "azure"]
    
    - primary: "azure"
      fallbacks: ["dashscope", "volcengine", "deepseek"]

# ═══════════════════════════════════════════════════════════════════════════════
# 成本控制配置
# ═══════════════════════════════════════════════════════════════════════════════
cost_control:
  
  # 每日预算 (USD)
  daily_budget:
    total: 100.0
    per_channel: 20.0
    alert_threshold: 0.8  # 80% 时告警
  
  # 每请求成本上限
  per_request_limits:
    chat: 0.10
    vision: 0.20
    embedding: 0.01
    batch: 1.00
  
  # 成本优化策略
  optimization:
    # 启用缓存减少重复调用
    cache_identical_requests: true
    cache_ttl_hours: 24
    
    # 批量合并小请求
    batch_small_requests: true
    batch_window_ms: 100
    min_batch_size: 5
    
    # 低峰时段使用 Spot
    use_spot_in_off_peak: true
    off_peak_hours: [0, 1, 2, 3, 4, 5, 6]
    
    # 自动选择性价比最高的模型
    auto_model_selection: true
    model_selection_strategy: "cost_first"  # cost_first | quality_first | balanced
```

### Provider 注册器实现

```python
# core/compute/provider_registry.py
"""
多云算力 Provider 注册器
设计原则：最大性价比、灵活配置、随时扩展
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

import httpx
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════════════
provider_requests = Counter(
    "compute_provider_requests_total",
    "Total requests per provider",
    ["provider", "model", "task_type", "status"]
)
provider_latency = Histogram(
    "compute_provider_latency_seconds",
    "Request latency per provider",
    ["provider", "model", "task_type"]
)
provider_cost = Counter(
    "compute_provider_cost_usd_total",
    "Total cost per provider in USD",
    ["provider", "model", "task_type"]
)
provider_health = Gauge(
    "compute_provider_health",
    "Provider health status (1=healthy, 0=unhealthy)",
    ["provider"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════
class TaskType(Enum):
    CHAT = "chat"
    VISION = "vision"
    EMBEDDING = "embedding"
    BATCH = "batch"
    GPU_COMPUTE = "gpu_compute"


class RoutingStrategy(Enum):
    COST_FIRST = "cost_first"
    PERFORMANCE_FIRST = "performance_first"
    BALANCED = "balanced"


@dataclass
class ProviderConfig:
    """Provider 配置数据类"""
    id: str
    name: str
    category: str  # domestic | foreign
    enabled: bool = True
    priority: int = 10
    api_key: str = ""
    base_url: str = ""
    endpoints: Dict[str, str] = field(default_factory=dict)
    models: Dict[str, List[Dict]] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)
    extra_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """模型配置数据类"""
    id: str
    name: str
    provider_id: str
    task_type: TaskType
    context_length: int = 4096
    cost_per_1k_tokens: float = 0.0
    cost_per_image: float = 0.0
    dimension: int = 0  # For embeddings
    max_tokens: int = 4096
    recommended_for: List[str] = field(default_factory=list)


@dataclass
class ComputeRequest:
    """算力请求数据类"""
    task_type: TaskType
    content: Any
    model_id: Optional[str] = None
    provider_id: Optional[str] = None
    max_cost: Optional[float] = None
    priority: str = "normal"  # realtime | normal | batch
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeResponse:
    """算力响应数据类"""
    success: bool
    result: Any
    provider_id: str
    model_id: str
    latency_ms: float
    cost_usd: float
    cached: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Base Provider Interface
# ═══════════════════════════════════════════════════════════════════════════════
class BaseComputeProvider(ABC):
    """算力 Provider 基类"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.http_client: Optional[httpx.AsyncClient] = None
        self._healthy = True
        self._last_health_check = 0
        self._circuit_breaker_failures = 0
        self._circuit_breaker_open_until = 0
    
    @property
    def provider_id(self) -> str:
        return self.config.id
    
    @property
    def is_healthy(self) -> bool:
        return self._healthy and time.time() > self._circuit_breaker_open_until
    
    async def initialize(self) -> None:
        """初始化 HTTP 客户端"""
        if not self.http_client:
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                limits=httpx.Limits(max_connections=100)
            )
    
    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    @abstractmethod
    async def chat(self, messages: List[Dict], model: str, **kwargs) -> Dict:
        """Chat completion"""
        pass
    
    @abstractmethod
    async def embed(self, texts: List[str], model: str, **kwargs) -> List[List[float]]:
        """Text embedding"""
        pass
    
    @abstractmethod
    async def vision(self, images: List[bytes], prompt: str, model: str, **kwargs) -> str:
        """Vision understanding"""
        pass
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            endpoint = self.config.extra_config.get("health_check", {}).get("endpoint")
            if endpoint and self.http_client:
                resp = await self.http_client.get(
                    endpoint,
                    headers=self._get_auth_headers(),
                    timeout=10.0
                )
                self._healthy = resp.status_code == 200
            else:
                self._healthy = True
        except Exception as e:
            logger.warning(f"Health check failed for {self.provider_id}: {e}")
            self._healthy = False
        
        provider_health.labels(provider=self.provider_id).set(1 if self._healthy else 0)
        self._last_health_check = time.time()
        return self._healthy
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取认证头"""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
    
    def _on_success(self) -> None:
        """成功时重置熔断器"""
        self._circuit_breaker_failures = 0
    
    def _on_failure(self) -> None:
        """失败时更新熔断器"""
        self._circuit_breaker_failures += 1
        if self._circuit_breaker_failures >= 3:
            self._circuit_breaker_open_until = time.time() + 30  # 30秒熔断
            logger.warning(f"Circuit breaker opened for {self.provider_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Implementations
# ═══════════════════════════════════════════════════════════════════════════════

class DashScopeProvider(BaseComputeProvider):
    """阿里云百炼 Provider"""
    
    async def chat(self, messages: List[Dict], model: str, **kwargs) -> Dict:
        await self.initialize()
        url = self.config.endpoints.get("chat")
        
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        resp = await self.http_client.post(
            url,
            headers=self._get_auth_headers(),
            json=body
        )
        resp.raise_for_status()
        return resp.json()
    
    async def embed(self, texts: List[str], model: str, **kwargs) -> List[List[float]]:
        await self.initialize()
        url = self.config.endpoints.get("embedding")
        
        # DashScope embedding API 格式
        body = {
            "model": model,
            "input": {"texts": texts},
            "parameters": {"text_type": "query"}
        }
        
        headers = self._get_auth_headers()
        headers["X-DashScope-DataInspection"] = "enable"
        
        resp = await self.http_client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        
        # 解析响应
        embeddings = data.get("output", {}).get("embeddings", [])
        return [e.get("embedding", []) for e in embeddings]
    
    async def vision(self, images: List[bytes], prompt: str, model: str, **kwargs) -> str:
        await self.initialize()
        url = self.config.endpoints.get("vision")
        
        import base64
        image_contents = []
        for img in images:
            b64 = base64.b64encode(img).decode()
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        
        body = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [*image_contents, {"type": "text", "text": prompt}]
            }],
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class VolcengineProvider(BaseComputeProvider):
    """火山方舟 Provider"""
    
    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
    
    async def chat(self, messages: List[Dict], model: str, **kwargs) -> Dict:
        await self.initialize()
        url = self.config.endpoints.get("chat")
        
        # 火山方舟使用 endpoint_id 而非 model
        endpoint_id = kwargs.pop("endpoint_id", None) or model
        
        body = {
            "model": endpoint_id,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        return resp.json()
    
    async def embed(self, texts: List[str], model: str, **kwargs) -> List[List[float]]:
        await self.initialize()
        url = self.config.endpoints.get("embedding")
        
        body = {
            "model": model,
            "input": texts
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return [e["embedding"] for e in data.get("data", [])]
    
    async def vision(self, images: List[bytes], prompt: str, model: str, **kwargs) -> str:
        await self.initialize()
        url = self.config.endpoints.get("vision")
        
        import base64
        image_contents = []
        for img in images:
            b64 = base64.b64encode(img).decode()
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        
        body = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [*image_contents, {"type": "text", "text": prompt}]
            }],
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class AzureOpenAIProvider(BaseComputeProvider):
    """Azure OpenAI Provider"""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        return {
            "api-key": self.config.api_key,
            "Content-Type": "application/json"
        }
    
    def _build_url(self, deployment: str, endpoint_type: str) -> str:
        """构建 Azure 端点 URL"""
        return f"{self.endpoint}/openai/deployments/{deployment}/{endpoint_type}?api-version={self.api_version}"
    
    async def chat(self, messages: List[Dict], model: str, **kwargs) -> Dict:
        await self.initialize()
        deployment = kwargs.pop("deployment", model)
        url = self._build_url(deployment, "chat/completions")
        
        body = {
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        return resp.json()
    
    async def embed(self, texts: List[str], model: str, **kwargs) -> List[List[float]]:
        await self.initialize()
        deployment = kwargs.pop("deployment", model)
        url = self._build_url(deployment, "embeddings")
        
        body = {"input": texts}
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return [e["embedding"] for e in data.get("data", [])]
    
    async def vision(self, images: List[bytes], prompt: str, model: str, **kwargs) -> str:
        await self.initialize()
        deployment = kwargs.pop("deployment", model)
        url = self._build_url(deployment, "chat/completions")
        
        import base64
        image_contents = []
        for img in images:
            b64 = base64.b64encode(img).decode()
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        
        body = {
            "messages": [{
                "role": "user",
                "content": [*image_contents, {"type": "text", "text": prompt}]
            }],
            "max_tokens": kwargs.get("max_tokens", 4096)
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


class DeepSeekProvider(BaseComputeProvider):
    """DeepSeek Provider (高性价比)"""
    
    async def chat(self, messages: List[Dict], model: str, **kwargs) -> Dict:
        await self.initialize()
        url = self.config.endpoints.get("chat")
        
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        return resp.json()
    
    async def embed(self, texts: List[str], model: str, **kwargs) -> List[List[float]]:
        # DeepSeek 暂无 embedding API，抛出异常
        raise NotImplementedError("DeepSeek does not provide embedding API")
    
    async def vision(self, images: List[bytes], prompt: str, model: str, **kwargs) -> str:
        await self.initialize()
        url = self.config.endpoints.get("vision")
        
        import base64
        image_contents = []
        for img in images:
            b64 = base64.b64encode(img).decode()
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
        
        body = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [*image_contents, {"type": "text", "text": prompt}]
            }],
            **kwargs
        }
        
        resp = await self.http_client.post(
            url, headers=self._get_auth_headers(), json=body
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Registry
# ═══════════════════════════════════════════════════════════════════════════════

class ComputeProviderRegistry:
    """
    多云算力 Provider 注册器
    
    功能：
    1. 统一管理多个 Provider
    2. 智能路由与负载均衡
    3. 成本优化与预算控制
    4. 故障转移与熔断
    5. 请求缓存
    """
    
    # Provider 类映射
    PROVIDER_CLASSES: Dict[str, Type[BaseComputeProvider]] = {
        "dashscope": DashScopeProvider,
        "volcengine": VolcengineProvider,
        "azure": AzureOpenAIProvider,
        "deepseek": DeepSeekProvider,
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self.providers: Dict[str, BaseComputeProvider] = {}
        self.models: Dict[str, ModelConfig] = {}
        self.config: Dict[str, Any] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 3600
        self._daily_cost: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """从 YAML 文件加载配置"""
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 注册所有 Provider
        for provider_id, provider_config in self.config.get("providers", {}).items():
            if provider_config.get("enabled", True):
                self.register_provider(provider_id, provider_config)
    
    def register_provider(self, provider_id: str, config: Dict[str, Any]) -> None:
        """注册 Provider"""
        provider_class = self.PROVIDER_CLASSES.get(provider_id)
        if not provider_class:
            logger.warning(f"Unknown provider: {provider_id}")
            return
        
        # 从环境变量获取 API Key
        auth_config = config.get("auth", {})
        api_key = None
        for env_var in auth_config.get("env_vars", []):
            api_key = os.environ.get(env_var)
            if api_key:
                break
        
        if not api_key:
            logger.warning(f"No API key found for provider: {provider_id}")
            return
        
        provider_config = ProviderConfig(
            id=provider_id,
            name=config.get("name", provider_id),
            category=config.get("category", "other"),
            enabled=config.get("enabled", True),
            priority=config.get("priority", 10),
            api_key=api_key,
            base_url=config.get("endpoints", {}).get("chat", ""),
            endpoints=config.get("endpoints", {}),
            models=config.get("models", {}),
            rate_limits=config.get("rate_limits", {}),
            extra_config=config
        )
        
        self.providers[provider_id] = provider_class(provider_config)
        
        # 注册模型
        for task_type, models in config.get("models", {}).items():
            for model in models:
                model_config = ModelConfig(
                    id=model["id"],
                    name=model["name"],
                    provider_id=provider_id,
                    task_type=TaskType(task_type if task_type != "llm" else "chat"),
                    context_length=model.get("context_length", 4096),
                    cost_per_1k_tokens=model.get("cost_per_1k_tokens", 0),
                    cost_per_image=model.get("cost_per_image", 0),
                    dimension=model.get("dimension", 0),
                    recommended_for=model.get("recommended_for", [])
                )
                self.models[f"{provider_id}/{model['id']}"] = model_config
        
        logger.info(f"Registered provider: {provider_id}")
    
    async def execute(self, request: ComputeRequest) -> ComputeResponse:
        """
        执行算力请求
        
        路由策略：
        1. 检查缓存
        2. 选择最优 Provider
        3. 执行请求
        4. 故障转移
        5. 记录成本
        """
        start_time = time.perf_counter()
        
        # 1. 检查缓存
        cache_key = self._get_cache_key(request)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                return ComputeResponse(
                    success=True,
                    result=cached["result"],
                    provider_id=cached["provider_id"],
                    model_id=cached["model_id"],
                    latency_ms=0,
                    cost_usd=0,
                    cached=True
                )
        
        # 2. 选择 Provider 和 Model
        provider, model = await self._select_provider_and_model(request)
        if not provider:
            return ComputeResponse(
                success=False,
                result=None,
                provider_id="",
                model_id="",
                latency_ms=0,
                cost_usd=0,
                error="No available provider"
            )
        
        # 3. 执行请求 (带故障转移)
        result = None
        error = None
        used_provider = provider
        used_model = model
        
        failover_chain = self._get_failover_chain(provider.provider_id)
        
        for provider_id in [provider.provider_id] + failover_chain:
            try:
                current_provider = self.providers.get(provider_id)
                if not current_provider or not current_provider.is_healthy:
                    continue
                
                result = await self._execute_task(current_provider, request, model.id)
                used_provider = current_provider
                current_provider._on_success()
                break
                
            except Exception as e:
                logger.warning(f"Provider {provider_id} failed: {e}")
                if current_provider:
                    current_provider._on_failure()
                error = str(e)
                continue
        
        # 4. 计算成本和延迟
        latency_ms = (time.perf_counter() - start_time) * 1000
        cost_usd = self._calculate_cost(request, used_model)
        
        # 5. 记录指标
        status = "success" if result else "error"
        provider_requests.labels(
            provider=used_provider.provider_id,
            model=used_model.id,
            task_type=request.task_type.value,
            status=status
        ).inc()
        
        provider_latency.labels(
            provider=used_provider.provider_id,
            model=used_model.id,
            task_type=request.task_type.value
        ).observe(latency_ms / 1000)
        
        if cost_usd > 0:
            provider_cost.labels(
                provider=used_provider.provider_id,
                model=used_model.id,
                task_type=request.task_type.value
            ).inc(cost_usd)
        
        # 6. 更新缓存
        if result and cache_key:
            self._cache[cache_key] = {
                "result": result,
                "provider_id": used_provider.provider_id,
                "model_id": used_model.id,
                "timestamp": time.time()
            }
        
        return ComputeResponse(
            success=result is not None,
            result=result,
            provider_id=used_provider.provider_id,
            model_id=used_model.id,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            error=error if not result else None
        )
    
    async def _select_provider_and_model(
        self, request: ComputeRequest
    ) -> tuple[Optional[BaseComputeProvider], Optional[ModelConfig]]:
        """选择最优 Provider 和 Model"""
        
        # 如果指定了 Provider 和 Model
        if request.provider_id and request.model_id:
            provider = self.providers.get(request.provider_id)
            model_key = f"{request.provider_id}/{request.model_id}"
            model = self.models.get(model_key)
            if provider and model and provider.is_healthy:
                return provider, model
        
        # 根据路由规则选择
        routing_rules = self.config.get("routing_rules", {})
        task_routing = routing_rules.get("task_routing", [])
        
        # 找到匹配的路由规则
        matching_rule = None
        for rule in task_routing:
            if rule.get("task_type") == request.task_type.value:
                matching_rule = rule
                break
        
        if not matching_rule:
            # 默认选择：按优先级选择可用的 Provider
            for provider in sorted(
                self.providers.values(),
                key=lambda p: p.config.priority
            ):
                if provider.is_healthy:
                    # 选择该 Provider 的默认模型
                    for model_key, model in self.models.items():
                        if model.provider_id == provider.provider_id and \
                           model.task_type == request.task_type:
                            return provider, model
            return None, None
        
        # 按规则选择
        strategy = self.config.get("global_strategy", {}).get(
            "routing_strategy", "cost_first"
        )
        
        candidates = []
        for provider_id in matching_rule.get("preferred_providers", []):
            provider = self.providers.get(provider_id)
            if not provider or not provider.is_healthy:
                continue
            
            for model_id in matching_rule.get("preferred_models", []):
                model_key = f"{provider_id}/{model_id}"
                model = self.models.get(model_key)
                if model:
                    # 检查成本限制
                    max_cost = request.max_cost or matching_rule.get("max_cost_per_request")
                    if max_cost and model.cost_per_1k_tokens > max_cost * 10:
                        continue
                    candidates.append((provider, model))
        
        if not candidates:
            return None, None
        
        # 根据策略排序
        if strategy == "cost_first":
            candidates.sort(key=lambda x: x[1].cost_per_1k_tokens)
        elif strategy == "performance_first":
            candidates.sort(key=lambda x: -x[1].context_length)
        
        return candidates[0]
    
    async def _execute_task(
        self, provider: BaseComputeProvider, request: ComputeRequest, model_id: str
    ) -> Any:
        """执行具体任务"""
        if request.task_type == TaskType.CHAT:
            return await provider.chat(
                messages=request.content,
                model=model_id,
                **request.metadata
            )
        elif request.task_type == TaskType.EMBEDDING:
            return await provider.embed(
                texts=request.content,
                model=model_id,
                **request.metadata
            )
        elif request.task_type == TaskType.VISION:
            return await provider.vision(
                images=request.content.get("images", []),
                prompt=request.content.get("prompt", ""),
                model=model_id,
                **request.metadata
            )
        else:
            raise ValueError(f"Unsupported task type: {request.task_type}")
    
    def _get_cache_key(self, request: ComputeRequest) -> str:
        """生成缓存键"""
        content_str = json.dumps(request.content, sort_keys=True, ensure_ascii=False)
        key_str = f"{request.task_type.value}:{content_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_failover_chain(self, primary_provider: str) -> List[str]:
        """获取故障转移链"""
        failover_chains = self.config.get("routing_rules", {}).get("failover_chains", [])
        for chain in failover_chains:
            if chain.get("primary") == primary_provider:
                return chain.get("fallbacks", [])
        return []
    
    def _calculate_cost(self, request: ComputeRequest, model: ModelConfig) -> float:
        """计算请求成本"""
        if request.task_type == TaskType.VISION:
            num_images = len(request.content.get("images", []))
            return model.cost_per_image * num_images
        elif request.task_type in [TaskType.CHAT, TaskType.EMBEDDING]:
            # 估算 token 数 (粗略)
            content_str = json.dumps(request.content, ensure_ascii=False)
            estimated_tokens = len(content_str) / 4
            return (estimated_tokens / 1000) * model.cost_per_1k_tokens
        return 0
    
    async def health_check_all(self) -> Dict[str, bool]:
        """检查所有 Provider 健康状态"""
        results = {}
        for provider_id, provider in self.providers.items():
            results[provider_id] = await provider.health_check()
        return results
    
    async def close_all(self) -> None:
        """关闭所有 Provider"""
        for provider in self.providers.values():
            await provider.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════════════════════════

_registry_instance: Optional[ComputeProviderRegistry] = None


def get_compute_registry() -> ComputeProviderRegistry:
    """获取全局 Provider Registry 实例"""
    global _registry_instance
    if _registry_instance is None:
        config_path = os.path.join(
            os.getcwd(), "core", "compute", "providers.yaml"
        )
        if os.path.exists(config_path):
            _registry_instance = ComputeProviderRegistry(config_path)
        else:
            _registry_instance = ComputeProviderRegistry()
    return _registry_instance


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════════

async def chat(
    messages: List[Dict],
    model: Optional[str] = None,
    provider: Optional[str] = None,
    max_cost: Optional[float] = None
) -> ComputeResponse:
    """便捷聊天接口"""
    registry = get_compute_registry()
    request = ComputeRequest(
        task_type=TaskType.CHAT,
        content=messages,
        model_id=model,
        provider_id=provider,
        max_cost=max_cost
    )
    return await registry.execute(request)


async def embed(
    texts: List[str],
    model: Optional[str] = None,
    provider: Optional[str] = None
) -> ComputeResponse:
    """便捷 Embedding 接口"""
    registry = get_compute_registry()
    request = ComputeRequest(
        task_type=TaskType.EMBEDDING,
        content=texts,
        model_id=model,
        provider_id=provider
    )
    return await registry.execute(request)


async def vision(
    images: List[bytes],
    prompt: str,
    model: Optional[str] = None,
    provider: Optional[str] = None
) -> ComputeResponse:
    """便捷视觉理解接口"""
    registry = get_compute_registry()
    request = ComputeRequest(
        task_type=TaskType.VISION,
        content={"images": images, "prompt": prompt},
        model_id=model,
        provider_id=provider
    )
    return await registry.execute(request)
```

---

## ⚡ GPU 算力需求与不瓶颈设计

### 不让算力成为瓶颈的策略

```yaml
# core/compute/cost_optimizer.yaml
# 成本优化策略配置

cost_optimizer:
  
  # ─────────────────────────────────────────────────────────────────────────────
  # 策略 1: 智能降级 (按算力可用性自动调整)
  # ─────────────────────────────────────────────────────────────────────────────
  auto_fallback:
    enabled: true
    rules:
      # 无 GPU 时降级到云 API
      - condition: "gpu_available = false"
        action: "route_to_cloud_api"
        providers: ["dashscope", "volcengine", "azure"]
        cost_impact: "按调用付费，无 GPU 成本"
      
      # GPU 显存不足时减少批量
      - condition: "gpu_vram < required_vram"
        action: "reduce_batch_size"
        settings:
          batch_size: 1
          use_fp16: true
          gradient_checkpointing: true
        cost_impact: "牺牲速度，节省显存"
      
      # 高成本任务自动选择便宜模型
      - condition: "estimated_cost > budget"
        action: "use_cheaper_model"
        model_downgrade_chain:
          - from: "gpt-4o"
            to: "gpt-4o-mini"
          - from: "qwen-max"
            to: "qwen-plus"
          - from: "qwen-vl-max"
            to: "qwen-vl-plus"
        cost_impact: "质量略降，成本大幅下降"
  
  # ─────────────────────────────────────────────────────────────────────────────
  # 策略 2: 缓存优化 (避免重复计算)
  # ─────────────────────────────────────────────────────────────────────────────
  caching:
    enabled: true
    
    # Embedding 缓存 (最大收益)
    embedding_cache:
      enabled: true
      backend: "redis"  # redis | memory | disk
      ttl_hours: 168    # 7 天
      max_size_gb: 10
      hit_rate_target: 0.7  # 目标命中率
      
    # LLM 响应缓存 (相同问题)
    llm_cache:
      enabled: true
      backend: "redis"
      ttl_hours: 24
      max_size_gb: 5
      similarity_threshold: 0.95  # 语义相似度阈值
      
    # VLM 图像缓存 (相同图像)
    vision_cache:
      enabled: true
      backend: "disk"
      ttl_hours: 72
      max_size_gb: 50
      image_hash_algorithm: "perceptual"  # 感知哈希
  
  # ─────────────────────────────────────────────────────────────────────────────
  # 策略 3: 批量合并 (减少调用次数)
  # ─────────────────────────────────────────────────────────────────────────────
  batching:
    enabled: true
    
    # 请求合并窗口
    merge_window_ms: 100
    min_batch_size: 5
    max_batch_size: 100
    
    # 按任务类型配置
    task_config:
      embedding:
        enabled: true
        max_batch_tokens: 8000
        
      chat:
        enabled: false  # 聊天通常不适合批量
        
      vision:
        enabled: true
        max_batch_images: 10
  
  # ─────────────────────────────────────────────────────────────────────────────
  # 策略 4: 时段调度 (利用低价时段)
  # ─────────────────────────────────────────────────────────────────────────────
  scheduling:
    enabled: true
    
    # 非实时任务延迟到低价时段
    off_peak_scheduling:
      enabled: true
      off_peak_hours: [0, 1, 2, 3, 4, 5, 6]  # UTC
      applicable_tasks: ["batch_embedding", "graphrag_build", "raptor_build"]
      
    # Spot 实例优先
    spot_preference:
      enabled: true
      spot_first_for: ["batch", "non_realtime"]
      max_wait_for_spot_minutes: 10
  
  # ─────────────────────────────────────────────────────────────────────────────
  # 策略 5: 预算控制 (硬性限制)
  # ─────────────────────────────────────────────────────────────────────────────
  budget_control:
    enabled: true
    
    # 全局预算
    global:
      daily_limit_usd: 100
      monthly_limit_usd: 2000
      alert_threshold: 0.8
      hard_stop_threshold: 0.95
      
    # 按 Channel 预算
    per_channel:
      daily_limit_usd: 20
      alert_threshold: 0.7
      
    # 按任务类型预算
    per_task_type:
      chat:
        daily_limit_usd: 30
      vision:
        daily_limit_usd: 40
      embedding:
        daily_limit_usd: 20
      batch:
        daily_limit_usd: 10
```

### 成本估算器实现

```python
# core/compute/cost_estimator.py
"""
成本估算器 - 在执行前预估成本，支持预算控制
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum


class CostTier(Enum):
    """成本层级"""
    FREE = "free"           # 缓存命中
    CHEAP = "cheap"         # < $0.001/请求
    MODERATE = "moderate"   # $0.001 - $0.01/请求
    EXPENSIVE = "expensive" # $0.01 - $0.10/请求
    VERY_EXPENSIVE = "very_expensive"  # > $0.10/请求


@dataclass
class CostEstimate:
    """成本估算结果"""
    estimated_cost_usd: float
    cost_tier: CostTier
    recommended_provider: str
    recommended_model: str
    alternatives: List[Dict[str, Any]]
    can_use_cache: bool
    cache_probability: float
    budget_remaining_usd: float
    budget_exceeded: bool
    cost_breakdown: Dict[str, float]
    optimization_suggestions: List[str]


class CostEstimator:
    """
    成本估算器
    
    功能：
    1. 预估请求成本
    2. 推荐最优方案
    3. 预算检查
    4. 优化建议
    """
    
    # 各 Provider 模型的成本配置 (USD per 1K tokens)
    COST_TABLE = {
        "dashscope": {
            "qwen-max": {"input": 0.02, "output": 0.06},
            "qwen-plus": {"input": 0.004, "output": 0.012},
            "qwen-turbo": {"input": 0.002, "output": 0.006},
            "qwen-vl-max": {"per_image": 0.01},
            "qwen-vl-plus": {"per_image": 0.004},
            "text-embedding-v3": {"input": 0.0007},
        },
        "volcengine": {
            "doubao-pro-256k": {"input": 0.005, "output": 0.009},
            "doubao-lite-128k": {"input": 0.0008, "output": 0.001},
            "doubao-vision-pro": {"per_image": 0.008},
            "doubao-vision-lite": {"per_image": 0.003},
            "doubao-embedding": {"input": 0.0005},
        },
        "azure": {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "text-embedding-3-large": {"input": 0.00013},
            "text-embedding-3-small": {"input": 0.00002},
        },
        "deepseek": {
            "deepseek-chat": {"input": 0.0001, "output": 0.0002},
            "deepseek-reasoner": {"input": 0.0004, "output": 0.0016},
            "deepseek-vl": {"per_image": 0.002},
        },
    }
    
    def __init__(self, budget_config: Dict[str, Any]):
        self.budget_config = budget_config
        self._daily_spent: Dict[str, float] = {}
    
    def estimate(
        self,
        task_type: str,
        content: Any,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        channel_id: Optional[str] = None
    ) -> CostEstimate:
        """
        估算请求成本
        
        Args:
            task_type: chat | embedding | vision
            content: 请求内容
            preferred_provider: 首选 Provider
            preferred_model: 首选模型
            channel_id: Channel ID (用于预算隔离)
        
        Returns:
            CostEstimate 对象
        """
        # 1. 估算 Token/Image 数量
        if task_type == "chat":
            input_tokens = self._estimate_tokens(content)
            output_tokens = input_tokens * 0.5  # 估算输出
        elif task_type == "embedding":
            input_tokens = self._estimate_tokens(content)
            output_tokens = 0
        elif task_type == "vision":
            num_images = len(content.get("images", []))
            input_tokens = self._estimate_tokens(content.get("prompt", ""))
            output_tokens = 500  # 估算输出
        else:
            input_tokens = 0
            output_tokens = 0
            num_images = 0
        
        # 2. 计算各方案成本
        alternatives = []
        for provider, models in self.COST_TABLE.items():
            for model, costs in models.items():
                if task_type == "vision" and "per_image" not in costs:
                    continue
                if task_type != "vision" and "per_image" in costs:
                    continue
                if task_type == "embedding" and "output" in costs:
                    continue
                    
                if "per_image" in costs:
                    cost = costs["per_image"] * num_images
                else:
                    cost = (
                        costs.get("input", 0) * input_tokens / 1000 +
                        costs.get("output", 0) * output_tokens / 1000
                    )
                
                alternatives.append({
                    "provider": provider,
                    "model": model,
                    "estimated_cost_usd": round(cost, 6),
                    "cost_tier": self._get_cost_tier(cost)
                })
        
        # 3. 排序选择最优
        alternatives.sort(key=lambda x: x["estimated_cost_usd"])
        
        # 4. 确定推荐方案
        if preferred_provider and preferred_model:
            recommended = next(
                (a for a in alternatives 
                 if a["provider"] == preferred_provider and a["model"] == preferred_model),
                alternatives[0] if alternatives else None
            )
        else:
            recommended = alternatives[0] if alternatives else None
        
        if not recommended:
            recommended = {"provider": "", "model": "", "estimated_cost_usd": 0}
        
        # 5. 检查预算
        budget_remaining = self._get_budget_remaining(channel_id)
        budget_exceeded = recommended["estimated_cost_usd"] > budget_remaining
        
        # 6. 检查缓存可能性
        can_use_cache, cache_prob = self._check_cache_probability(task_type, content)
        
        # 7. 生成优化建议
        suggestions = self._generate_suggestions(
            task_type, 
            recommended["estimated_cost_usd"],
            alternatives,
            can_use_cache
        )
        
        return CostEstimate(
            estimated_cost_usd=recommended["estimated_cost_usd"],
            cost_tier=self._get_cost_tier(recommended["estimated_cost_usd"]),
            recommended_provider=recommended["provider"],
            recommended_model=recommended["model"],
            alternatives=alternatives[:5],  # Top 5
            can_use_cache=can_use_cache,
            cache_probability=cache_prob,
            budget_remaining_usd=budget_remaining,
            budget_exceeded=budget_exceeded,
            cost_breakdown={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "num_images": num_images if task_type == "vision" else 0
            },
            optimization_suggestions=suggestions
        )
    
    def _estimate_tokens(self, content: Any) -> int:
        """估算 Token 数量 (粗略)"""
        if isinstance(content, str):
            return len(content) // 4
        elif isinstance(content, list):
            total = 0
            for item in content:
                if isinstance(item, dict):
                    total += len(str(item.get("content", ""))) // 4
                else:
                    total += len(str(item)) // 4
            return total
        return 0
    
    def _get_cost_tier(self, cost: float) -> CostTier:
        """获取成本层级"""
        if cost == 0:
            return CostTier.FREE
        elif cost < 0.001:
            return CostTier.CHEAP
        elif cost < 0.01:
            return CostTier.MODERATE
        elif cost < 0.10:
            return CostTier.EXPENSIVE
        else:
            return CostTier.VERY_EXPENSIVE
    
    def _get_budget_remaining(self, channel_id: Optional[str]) -> float:
        """获取剩余预算"""
        daily_limit = self.budget_config.get("global", {}).get("daily_limit_usd", 100)
        spent = sum(self._daily_spent.values())
        return max(0, daily_limit - spent)
    
    def _check_cache_probability(self, task_type: str, content: Any) -> tuple[bool, float]:
        """检查缓存命中可能性"""
        # 简化实现，实际应检查缓存
        if task_type == "embedding":
            return True, 0.7  # Embedding 缓存命中率高
        elif task_type == "chat":
            return True, 0.3  # Chat 缓存命中率中等
        elif task_type == "vision":
            return True, 0.5  # Vision 按图像哈希
        return False, 0
    
    def _generate_suggestions(
        self,
        task_type: str,
        estimated_cost: float,
        alternatives: List[Dict],
        can_use_cache: bool
    ) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        # 缓存建议
        if can_use_cache:
            suggestions.append("✅ 启用缓存可节省重复请求成本")
        
        # 模型降级建议
        if estimated_cost > 0.01 and len(alternatives) > 1:
            cheaper = alternatives[0]
            if cheaper["estimated_cost_usd"] < estimated_cost * 0.5:
                suggestions.append(
                    f"💡 使用 {cheaper['provider']}/{cheaper['model']} "
                    f"可节省 {(1 - cheaper['estimated_cost_usd']/estimated_cost)*100:.0f}% 成本"
                )
        
        # 批量处理建议
        if task_type == "embedding":
            suggestions.append("📦 批量处理 Embedding 可获得更优单价")
        
        # Spot 实例建议
        if task_type in ["batch", "non_realtime"]:
            suggestions.append("⏰ 非实时任务可使用 Spot 实例节省 30-70% GPU 成本")
        
        return suggestions


# 便捷函数
def estimate_cost(
    task_type: str,
    content: Any,
    preferred_provider: Optional[str] = None,
    preferred_model: Optional[str] = None
) -> CostEstimate:
    """
    估算请求成本
    
    Example:
        >>> estimate = estimate_cost(
        ...     task_type="chat",
        ...     content=[{"role": "user", "content": "Hello"}]
        ... )
        >>> print(f"Estimated: ${estimate.estimated_cost_usd:.4f}")
        >>> print(f"Recommended: {estimate.recommended_provider}/{estimate.recommended_model}")
    """
    estimator = CostEstimator({
        "global": {"daily_limit_usd": 100}
    })
    return estimator.estimate(task_type, content, preferred_provider, preferred_model)
```

---

## 📊 100TB+ 数据处理架构

### 数据分层存储

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        100TB+ DATA PROCESSING ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   HOT TIER (SSD/NVMe) - 5TB                                                 │
│   ├── 最近 7 天摄入的文档                                                    │
│   ├── 高频访问的向量索引                                                     │
│   └── 活跃 Channel 的知识库                                                  │
│                                                                              │
│   WARM TIER (HDD/S3 Standard) - 25TB                                         │
│   ├── 30 天内的历史数据                                                      │
│   ├── 中频访问的知识库                                                       │
│   └── 领域知识图谱                                                           │
│                                                                              │
│   COLD TIER (S3 Glacier/Archive) - 70TB+                                     │
│   ├── 归档历史数据                                                           │
│   ├── 合规保留数据                                                           │
│   └── 备份与灾备                                                             │
│                                                                              │
│   ════════════════════════════════════════════════════════════════════════  │
│                                                                              │
│   VECTOR INDEX STRATEGY                                                      │
│   ├── Qdrant: 主向量库 (HNSW + 量化)                                         │
│   ├── Milvus: 超大规模备选 (IVF_PQ)                                          │
│   └── Elasticsearch: 关键词 + 混合检索                                       │
│                                                                              │
│   PROCESSING PIPELINE                                                        │
│   ├── Ingestion: Ray Data + Spark                                            │
│   ├── Embedding: Distributed BGE-M3                                          │
│   ├── VLM Processing: Batched API calls                                      │
│   └── GraphRAG: Incremental update                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 实施检查清单

### Phase 0: 算力基础设施 (1 周)
- [ ] 创建 `core/compute/` 模块目录
- [ ] 实现 `providers.yaml` 配置文件
- [ ] 实现 `ComputeProviderRegistry` 核心类
- [ ] 实现四个 Provider: DashScope, Volcengine, Azure, DeepSeek
- [ ] 实现 `CostEstimator` 成本估算器
- [ ] 集成到现有 `LLMGateway`
- [ ] 添加 Prometheus 监控指标

### Phase 1: 基础设施 (2 周)
- [ ] 扩展 `core/domains/` 模块目录结构
- [ ] 实现 `DomainInterpreterRegistry` 基类
- [ ] 定义领域本体 YAML Schema
- [ ] 集成 GPU 策略配置

### Phase 2: 核心能力 (4 周)
- [ ] 实现多模态垂直解读器
- [ ] 命理领域示例完整实现
- [ ] 四联漫画领域示例完整实现
- [ ] 领域感知的 Chunk 策略

### Phase 3: 规模化 (4 周)
- [ ] 分布式 Embedding 生成
- [ ] 增量 GraphRAG 更新
- [ ] 100TB 数据测试验证
- [ ] GPU 弹性扩展集成

### Phase 4: 优化与监控 (2 周)
- [ ] 性能基准测试
- [ ] 成本优化
- [ ] 监控面板
- [ ] 文档与培训

---

## 📝 使用示例

### 1. 注册新垂直领域

```python
from core.domains.registry import DomainInterpreterRegistry

# 注册命理领域
registry = DomainInterpreterRegistry()
registry.register_domain(
    domain_id="metaphysics_chinese",
    ontology_path="core/domains/metaphysics/ontology.yaml",
    interpreter_class="MetaphysicsInterpreter"
)
```

### 2. 执行垂直解读

```python
from core.domains import interpret_document

result = await interpret_document(
    content=image_bytes,
    content_type="image",
    domain_id="metaphysics_chinese",
    interpretation_depth="deep",
    enable_narrative=True,
    enable_knowledge_linking=True
)

print(result.narrative.detailed_interpretation)
# Output: 
# "本图展示了中国传统命理学中关于'天运周期'的核心概念。
#  图中道士形象代表古代术数传承者，其双手合十的姿态暗示
#  对天机的敬畏。文字叙述揭示了三个关键知识点：
#  1. 天运循环的漫长性与复杂性
#  2. 古代天才发现规律的罕见性  
#  3. 秘而不宣的传承传统
#  对话气泡中的'窥天机'与'遭天谴'体现了传统文化中
#  对宇宙规律的神秘主义态度..."
```

---

## 🔐 注意事项

### 算力 Provider 相关
1. **API Key 安全**: 所有 API Key 必须通过环境变量配置，禁止硬编码
2. **成本监控**: 每日检查成本报告，设置预算告警
3. **故障转移**: 确保每个 Provider 至少有一个备选
4. **延迟监控**: 监控各 Provider 延迟，及时发现问题
5. **数据合规**: 中国境内数据优先使用国内 Provider

### 垂直领域相关
1. **GPU 资源标注**: 所有需要 GPU 的能力必须在 UI 中明确标注
2. **降级方案**: 每个 GPU 能力必须有 CPU/云端降级方案
3. **成本估算**: 大规模处理前必须提供成本预估
4. **数据隔离**: 垂直领域知识库必须支持 Channel 隔离
5. **合规审计**: 命理等敏感领域需要内容合规检查

---

## 📊 监控与告警

### Grafana Dashboard 配置

```yaml
# 算力 Provider 监控面板
dashboards:
  compute_providers:
    panels:
      - title: "Provider 请求量"
        query: "sum(rate(compute_provider_requests_total[5m])) by (provider)"
        
      - title: "Provider 延迟 P95"
        query: "histogram_quantile(0.95, rate(compute_provider_latency_seconds_bucket[5m]))"
        
      - title: "每日成本累计"
        query: "sum(compute_provider_cost_usd_total) by (provider)"
        alert:
          - name: "DailyCostExceeded"
            condition: "> 80"
            message: "每日成本已超过 80%"
        
      - title: "Provider 健康状态"
        query: "compute_provider_health"
        alert:
          - name: "ProviderUnhealthy"
            condition: "== 0"
            message: "Provider 不健康"
        
      - title: "缓存命中率"
        query: "sum(compute_cache_hits_total) / sum(compute_requests_total)"
        
      - title: "成本节省 (通过缓存)"
        query: "sum(compute_cache_cost_saved_usd_total)"
```

---

*文档由 OmniRAG AI 设计师生成 | 2025-12-14 | v2.0*
