# OmniRAG 垂直领域增强 - 第二阶段开发指南

> **版本**: v1.0 | **日期**: 2025-12-14
> **阶段目标**: 领域抽象层设计 + 命理领域实现 + 真实数据验证
> **预计周期**: 3 周
> **依赖**: Phase 1 完成（多云 Provider + 成本追踪）
> **核心原则**: 共同能力在 core，差分能力在领域

---

## 🎯 第二阶段总览

### 阶段定位

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2: DOMAIN ABSTRACTION & METAPHYSICS                │
│                   "抽象层要通用，领域实现要专业"                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Phase 2 分为 4 个子阶段:                                                   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Phase 2.1: 理解 + 设计 (Week 1, Day 1-3)                            │   │
│   │   ├── 分析 core/vision/, core/retrieval/ 现有实现                   │   │
│   │   ├── 设计领域抽象层架构                                            │   │
│   │   ├── 定义 BaseDomainInterpreter 接口                               │   │
│   │   └── 设计本体 Schema 规范                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Phase 2.2: 共同模块实现 (Week 1, Day 4-7)                           │   │
│   │   ├── 创建 core/domains/ 模块结构                                   │   │
│   │   ├── 实现 BaseDomainInterpreter 基类                               │   │
│   │   ├── 实现 DomainRegistry 注册器                                    │   │
│   │   ├── 实现 OntologySchema 验证器                                    │   │
│   │   └── 实现 NarrativeEngine 叙事引擎                                 │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Phase 2.3: 命理领域实现 (Week 2)                                    │   │
│   │   ├── 设计命理本体 (ontology.yaml)                                  │   │
│   │   ├── 构建命理知识库 (天干/地支/五行/神煞)                          │   │
│   │   ├── 实现 MetaphysicsInterpreter                                   │   │
│   │   └── 真实命理图片解读测试                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Phase 2.4: 集成与验证 (Week 3)                                      │   │
│   │   ├── 与 Phase 1 算力层集成                                         │   │
│   │   ├── 端到端命理解读流程测试                                        │   │
│   │   ├── 性能优化与成本分析                                            │   │
│   │   └── 回归测试 + 文档完善                                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 架构集成原则回顾

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      共同能力 vs 差分能力 划分                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   共同能力 (core/domains/*.py)              差分能力 (core/domains/{domain}/)│
│   ═══════════════════════════               ═══════════════════════════════ │
│                                                                              │
│   ✅ BaseDomainInterpreter                  ✅ MetaphysicsInterpreter        │
│      - 定义统一接口                            - 命理特有解读逻辑            │
│      - 所有领域必须继承                        - 天干地支识别               │
│                                                                              │
│   ✅ DomainRegistry                         ✅ metaphysics/ontology.yaml     │
│      - 统一注册/发现机制                       - 命理专属本体定义            │
│      - 所有领域共用                                                          │
│                                                                              │
│   ✅ OntologySchema                         ✅ metaphysics/knowledge/        │
│      - 本体结构规范                            - 命理术语知识库              │
│      - 校验所有领域本体                        - 五行生克关系               │
│                                                                              │
│   ✅ NarrativeEngine                        ✅ ComicInterpreter (Phase 3)    │
│      - 通用叙事重构                            - 漫画特有解读逻辑            │
│      - 所有领域可复用                          - 分格检测/对话提取          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Phase 2.1: 理解现有实现 + 设计领域抽象层 (Day 1-3)

### 2.1.1 目标

在实现领域抽象层之前，深入理解 core 中已有的视觉处理、检索增强模块，确保新设计与现有架构无缝集成。

### 2.1.2 分析 core/vision/ 模块

#### 任务清单

```yaml
分析任务:
  目标: 理解现有视觉处理能力，识别领域扩展点
  
  文件列表:
    - core/vision/layout_analyzer.py
    - core/vision/yolo_detector.py
    - core/vision/layoutlm_parser.py
    - core/vision/table.py
    - core/vision/__init__.py
  
  理解要点:
    1. LayoutElement 数据结构:
       - 现有字段有哪些？
       - 是否支持扩展属性？
       - 如何添加「领域类型」字段？
    
    2. 区域检测逻辑:
       - layout_analyzer.py 如何分割页面？
       - 检测结果如何传递给下游？
       - 如何注入「领域感知」逻辑？
    
    3. YOLO 检测器:
       - 当前检测哪些对象？
       - 是否可扩展检测类别？
       - 如何添加「命理符号」检测？
    
    4. 表格处理:
       - table.py 如何处理表格？
       - 命理图表（如八字排盘）如何复用？
  
  输出物:
    - vision_module_class_diagram.md (Mermaid 类图)
    - vision_extension_points.md (扩展点分析)
```

#### 代码分析模板

```python
# 分析脚本: scripts/analyze_vision_module.py
"""
分析 core/vision/ 模块结构
生成扩展点报告
"""

import ast
import os
from pathlib import Path


def analyze_module(module_path: str) -> dict:
    """分析 Python 模块结构"""
    result = {
        "classes": [],
        "functions": [],
        "imports": [],
        "extension_points": []
    }
    
    with open(module_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_info = {
                "name": node.name,
                "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                "docstring": ast.get_docstring(node)
            }
            result["classes"].append(class_info)
            
            # 识别扩展点
            if any(m.startswith("_") and not m.startswith("__") for m in class_info["methods"]):
                result["extension_points"].append({
                    "class": node.name,
                    "type": "protected_methods",
                    "note": "可被子类覆盖"
                })
        
        elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
            result["functions"].append({
                "name": node.name,
                "args": [arg.arg for arg in node.args.args],
                "docstring": ast.get_docstring(node)
            })
    
    return result


def generate_report():
    """生成分析报告"""
    vision_path = Path("core/vision")
    report = []
    
    for py_file in vision_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        
        analysis = analyze_module(str(py_file))
        report.append({
            "file": py_file.name,
            "analysis": analysis
        })
    
    return report


if __name__ == "__main__":
    report = generate_report()
    
    # 输出 Markdown 报告
    print("# core/vision/ 模块分析报告\n")
    
    for item in report:
        print(f"## {item['file']}\n")
        
        if item['analysis']['classes']:
            print("### 类定义\n")
            for cls in item['analysis']['classes']:
                print(f"- **{cls['name']}**")
                if cls['bases']:
                    print(f"  - 继承: {', '.join(cls['bases'])}")
                print(f"  - 方法: {', '.join(cls['methods'][:5])}...")
                print()
        
        if item['analysis']['extension_points']:
            print("### 扩展点\n")
            for ext in item['analysis']['extension_points']:
                print(f"- {ext['class']}: {ext['note']}")
            print()
```

### 2.1.3 分析 core/retrieval/ 模块

#### 任务清单

```yaml
分析任务:
  目标: 理解现有检索增强能力，设计领域增强检索

  文件列表:
    - core/retrieval/graph.py
    - core/retrieval/multimodal/embedder.py
    - core/retrieval/multimodal/retriever.py
    - core/retrieval/nodes/

  理解要点:
    1. 检索流程:
       - 从 Query 到结果的完整链路
       - 多模态检索如何工作？
       - 图检索 (GraphRAG) 如何集成？
    
    2. Embedding 生成:
       - multimodal/embedder.py 如何处理图像？
       - 是否支持领域感知 Embedding？
       - 如何添加领域元数据到 Embedding？
    
    3. 检索器接口:
       - Retriever 基类/接口定义？
       - 如何实现「领域增强检索」？
       - 检索结果如何与解读器对接？
    
    4. 与 LangGraph 的关系:
       - graph.py 中的状态定义
       - 检索节点如何编排？
       - 领域解读节点如何加入？

  输出物:
    - retrieval_flow_diagram.md (检索流程图)
    - retrieval_domain_enhancement_design.md (领域增强设计)
```

### 2.1.4 分析 core/ingestion/ 模块

#### 任务清单

```yaml
分析任务:
  目标: 理解文档摄入流程，设计领域感知处理器

  文件列表:
    - core/ingestion/graph.py
    - core/ingestion/processors/
    - core/ingestion/state_factory.py
    - core/ingestion/nodes/

  理解要点:
    1. 摄入流程:
       - 文档如何进入系统？
       - 处理器 (Processor) 链如何工作？
       - 结果如何存储？
    
    2. 处理器接口:
       - Processor 基类定义？
       - 如何添加新处理器？
       - 处理器如何获取领域上下文？
    
    3. 节点定义:
       - 各节点的职责？
       - 如何添加「领域检测」节点？
       - 如何添加「领域解读」节点？

  输出物:
    - ingestion_processor_interface.md (处理器接口规范)
    - domain_aware_processor_design.md (领域感知处理器设计)
```

### 2.1.5 设计领域抽象层架构

基于以上分析，设计 `core/domains/` 模块的完整架构。

#### 架构设计图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOMAIN ABSTRACTION LAYER                              │
│                          core/domains/ 架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        Registry Layer                                │   │
│   │                     (领域注册与发现)                                 │   │
│   │                                                                      │   │
│   │   DomainRegistry                                                     │   │
│   │   ├── register(domain_id, interpreter_cls, ontology_path)           │   │
│   │   ├── get(domain_id) -> BaseDomainInterpreter                       │   │
│   │   ├── list_domains() -> List[DomainInfo]                            │   │
│   │   └── auto_detect(content) -> Optional[str]  # 自动检测领域         │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                                      ▼                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      Interpreter Layer                               │   │
│   │                     (领域解读器接口)                                 │   │
│   │                                                                      │   │
│   │   BaseDomainInterpreter (Abstract)                                   │   │
│   │   ├── domain_id: str                                                 │   │
│   │   ├── ontology: OntologySchema                                       │   │
│   │   │                                                                  │   │
│   │   │ # 核心抽象方法 (子类必须实现)                                    │   │
│   │   ├── async decompose(content) -> DecompositionResult               │   │
│   │   ├── async understand(decomposed) -> SemanticResult                │   │
│   │   ├── async interpret(content) -> InterpretationResult              │   │
│   │   │                                                                  │   │
│   │   │ # 可选覆盖方法 (有默认实现)                                      │   │
│   │   ├── async reconstruct_narrative(understood) -> NarrativeResult    │   │
│   │   └── async augment_knowledge(interpreted) -> AugmentedResult       │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│                     ┌────────────────┴────────────────┐                     │
│                     ▼                                  ▼                     │
│   ┌─────────────────────────────┐   ┌─────────────────────────────┐        │
│   │   MetaphysicsInterpreter    │   │    ComicInterpreter         │        │
│   │   (命理领域)                 │   │    (漫画领域 - Phase 3)     │        │
│   │                             │   │                             │        │
│   │   - 天干地支识别            │   │    - 分格检测               │        │
│   │   - 五行关系推理            │   │    - 对话气泡识别           │        │
│   │   - 命理术语解读            │   │    - 起承转合分析           │        │
│   └─────────────────────────────┘   └─────────────────────────────┘        │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       Schema Layer                                   │   │
│   │                     (本体与叙事)                                     │   │
│   │                                                                      │   │
│   │   OntologySchema                      NarrativeEngine                │   │
│   │   ├── entities: List[EntityDef]       ├── reconstruct(data, schema) │   │
│   │   ├── relations: List[RelationDef]    ├── templates: Dict           │   │
│   │   ├── attributes: List[AttributeDef]  └── format_output(style)      │   │
│   │   ├── validate(data) -> bool                                         │   │
│   │   └── from_yaml(path) -> OntologySchema                              │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                       Data Types                                     │   │
│   │                     (数据结构定义)                                   │   │
│   │                                                                      │   │
│   │   @dataclass DecompositionResult     @dataclass SemanticResult      │   │
│   │   ├── regions: List[Region]          ├── entities: List[Entity]     │   │
│   │   ├── texts: Dict[str, str]          ├── relations: List[Relation]  │   │
│   │   └── visual_elements: List[...]     └── attributes: Dict           │   │
│   │                                                                      │   │
│   │   @dataclass InterpretationResult    @dataclass NarrativeResult     │   │
│   │   ├── decomposition: ...             ├── summary: str               │   │
│   │   ├── semantics: ...                 ├── detailed: str              │   │
│   │   ├── narrative: ...                 ├── knowledge_points: List     │   │
│   │   └── metadata: Dict                 └── confidence: float          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 目录结构设计

```
core/domains/
├── __init__.py                     # 模块入口，导出公共接口
├── registry.py                     # DomainRegistry 领域注册器
├── base_interpreter.py             # BaseDomainInterpreter 基类
├── ontology_schema.py              # OntologySchema 本体定义
├── narrative_engine.py             # NarrativeEngine 叙事引擎
├── types.py                        # 数据类型定义
├── exceptions.py                   # 领域相关异常
│
├── metaphysics/                    # 命理领域 (Phase 2.3)
│   ├── __init__.py
│   ├── interpreter.py              # MetaphysicsInterpreter
│   ├── ontology.yaml               # 命理本体定义
│   ├── visual_rules.yaml           # 视觉识别规则
│   └── knowledge/                  # 命理知识库
│       ├── tiangan.yaml            # 天干
│       ├── dizhi.yaml              # 地支
│       ├── wuxing.yaml             # 五行
│       ├── shenshas.yaml           # 神煞
│       └── relations.yaml          # 关系规则
│
├── comic/                          # 漫画领域 (Phase 3)
│   ├── __init__.py
│   ├── interpreter.py
│   ├── ontology.yaml
│   └── panel_detector.py
│
└── _template/                      # 新领域模板
    ├── __init__.py.template
    ├── interpreter.py.template
    └── ontology.yaml.template
```

### 2.1.6 定义 BaseDomainInterpreter 接口

#### 接口设计文档

```yaml
# docs/tech/base_domain_interpreter_spec.md

BaseDomainInterpreter 接口规范:
  
  版本: v1.0
  设计原则:
    - 所有领域解读器必须继承此基类
    - 抽象方法强制子类实现领域特有逻辑
    - 可选方法提供默认实现，子类可覆盖
    - 与 Phase 1 算力层无缝集成

  核心属性:
    domain_id:
      类型: str
      描述: 领域唯一标识符
      示例: "metaphysics_chinese", "comic_four_panel"
      约束: 只能包含小写字母、数字、下划线
    
    domain_name:
      类型: str
      描述: 领域显示名称
      示例: "中国传统命理", "四联漫画"
    
    ontology:
      类型: OntologySchema
      描述: 领域本体定义
      加载: 从 ontology.yaml 自动加载
    
    gpu_requirements:
      类型: GPURequirements
      描述: GPU 资源需求声明
      字段:
        - min_vram_gb: int
        - recommended_vram_gb: int
        - reason: str

  抽象方法 (必须实现):
    
    decompose:
      签名: "async def decompose(self, content: ContentInput) -> DecompositionResult"
      描述: 内容分解 - 将输入拆分为结构化区域和元素
      输入:
        content: ContentInput
          - type: "image" | "text" | "pdf_page"
          - data: bytes | str
          - context: Optional[Dict]  # 上下文信息
      输出:
        DecompositionResult:
          - regions: List[Region]        # 检测到的区域
          - texts: Dict[str, str]        # OCR 提取的文本
          - visual_elements: List[VisualElement]  # 视觉元素
      
      实现指南:
        - 图像输入: 调用 VLM 进行区域检测和 OCR
        - 文本输入: 分段、识别术语、标注结构
        - 应利用 Phase 1 的 ComputeProvider
    
    understand:
      签名: "async def understand(self, decomposed: DecompositionResult) -> SemanticResult"
      描述: 语义理解 - 基于本体抽取实体和关系
      输入:
        decomposed: DecompositionResult (来自 decompose)
      输出:
        SemanticResult:
          - entities: List[Entity]       # 识别的实体
          - relations: List[Relation]    # 实体间关系
          - attributes: Dict[str, Any]   # 属性信息
      
      实现指南:
        - 根据 ontology.entities 识别实体
        - 根据 ontology.relations 推断关系
        - 使用领域知识库增强理解
    
    interpret:
      签名: "async def interpret(self, content: ContentInput) -> InterpretationResult"
      描述: 完整解读 - 组合 decompose + understand + narrative
      输入:
        content: ContentInput
      输出:
        InterpretationResult:
          - decomposition: DecompositionResult
          - semantics: SemanticResult
          - narrative: NarrativeResult
          - metadata: InterpretationMetadata
      
      实现指南:
        - 通常调用 decompose -> understand -> reconstruct_narrative
        - 可以根据领域特点优化流程
        - 记录处理时间、成本等元数据

  可选方法 (有默认实现):
    
    reconstruct_narrative:
      签名: "async def reconstruct_narrative(self, understood: SemanticResult) -> NarrativeResult"
      默认实现: 使用 NarrativeEngine 通用叙事重构
      覆盖场景: 领域有特殊叙事结构时
    
    augment_knowledge:
      签名: "async def augment_knowledge(self, interpreted: InterpretationResult) -> AugmentedResult"
      默认实现: 链接到知识图谱，补充背景知识
      覆盖场景: 领域有专属知识库时
    
    validate_input:
      签名: "def validate_input(self, content: ContentInput) -> ValidationResult"
      默认实现: 基本格式验证
      覆盖场景: 领域有特殊输入要求时
    
    estimate_cost:
      签名: "def estimate_cost(self, content: ContentInput) -> CostEstimate"
      默认实现: 使用 Phase 1 的 CostEstimator
      覆盖场景: 领域有特殊成本计算逻辑时

  生命周期方法:
    
    __init__:
      描述: 初始化解读器
      流程:
        1. 加载 ontology.yaml
        2. 验证本体结构
        3. 加载领域知识库
        4. 初始化算力 Provider
    
    setup:
      签名: "async def setup(self) -> None"
      描述: 异步初始化（如预热模型）
    
    teardown:
      签名: "async def teardown(self) -> None"
      描述: 清理资源
```

### 2.1.7 设计本体 Schema 规范

#### OntologySchema 规范

```yaml
# docs/tech/ontology_schema_spec.md

OntologySchema 规范:
  
  版本: v1.0
  文件格式: YAML
  校验: JSON Schema + 自定义验证器

  顶层结构:
    domain_id: str           # 必须与目录名一致
    domain_name: str
    domain_name_en: str
    version: str             # 语义版本号
    
    ontology:                # 本体核心定义
      entities: [...]
      relations: [...]
      attributes: [...]
    
    visual_schema:           # 视觉识别规范
      art_styles: [...]
      visual_elements: [...]
      composition_patterns: [...]
    
    narrative_schema:        # 叙事结构规范
      discourse_types: [...]
      knowledge_density: str
      temporal_structure: str
    
    interpretation_rules:    # 解读规则
      - trigger: str
        action: str
        output_format: str
    
    gpu_requirements:        # GPU 需求
      min_vram_gb: int
      recommended_vram_gb: int
      reason: str

  entities 定义:
    格式:
      - id: str              # 实体类型 ID
        name: str            # 显示名称
        description: str     # 描述
        parent: Optional[str]  # 父类型 ID（支持继承）
        attributes:          # 该实体类型的属性
          - id: str
            name: str
            type: str        # string, number, boolean, enum, list
            enum_values: Optional[List[str]]
            required: bool
        examples: List[str]  # 示例
    
    示例 (命理):
      - id: "tiangan"
        name: "天干"
        description: "甲乙丙丁戊己庚辛壬癸十天干"
        attributes:
          - id: "wuxing"
            name: "五行属性"
            type: "enum"
            enum_values: ["木", "火", "土", "金", "水"]
            required: true
          - id: "yinyang"
            name: "阴阳属性"
            type: "enum"
            enum_values: ["阳", "阴"]
            required: true
        examples: ["甲", "乙", "丙"]

  relations 定义:
    格式:
      - id: str              # 关系类型 ID
        name: str
        description: str
        source_types: List[str]   # 源实体类型
        target_types: List[str]   # 目标实体类型
        properties:          # 关系属性
          - id: str
            name: str
            type: str
        symmetric: bool      # 是否对称
        transitive: bool     # 是否传递
    
    示例 (命理):
      - id: "sheng"
        name: "相生"
        description: "五行相生关系：木生火，火生土，土生金，金生水，水生木"
        source_types: ["wuxing"]
        target_types: ["wuxing"]
        symmetric: false
        transitive: false
      
      - id: "ke"
        name: "相克"
        description: "五行相克关系：木克土，土克水，水克火，火克金，金克木"
        source_types: ["wuxing"]
        target_types: ["wuxing"]
        symmetric: false
        transitive: false

  校验规则:
    - domain_id 必须唯一
    - entity.id 在本体内唯一
    - relation 的 source_types/target_types 必须引用已定义的 entity
    - 循环引用检测
    - 属性类型验证
```

### 2.1.8 数据库 Schema 扩展

基于领域抽象层设计，扩展 Phase 1 的数据库 Schema。

```sql
-- 迁移脚本: core/storage/migrations/002_domain_infrastructure.sql

-- ═══════════════════════════════════════════════════════════════════════════════
-- 领域解读记录表
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS domain_interpretations (
    id SERIAL PRIMARY KEY,
    
    -- 请求标识
    request_id TEXT NOT NULL UNIQUE,        -- UUID
    channel_id TEXT,
    user_id TEXT,
    
    -- 领域信息
    domain_id TEXT NOT NULL,
    
    -- 输入内容
    content_type TEXT NOT NULL,             -- image, text, pdf_page
    content_hash TEXT NOT NULL,             -- 内容哈希，用于缓存
    content_size_bytes INTEGER,
    
    -- 解读结果 (JSON)
    decomposition JSONB,                    -- DecompositionResult
    semantics JSONB,                        -- SemanticResult
    narrative JSONB,                        -- NarrativeResult
    
    -- 识别的实体和关系
    entities_count INTEGER DEFAULT 0,
    relations_count INTEGER DEFAULT 0,
    
    -- 性能指标
    total_latency_ms INTEGER,
    decompose_latency_ms INTEGER,
    understand_latency_ms INTEGER,
    narrative_latency_ms INTEGER,
    
    -- 成本 (关联到 compute_cost_records)
    total_cost_usd DECIMAL(10, 6),
    
    -- 质量指标
    confidence_score DECIMAL(3, 2),         -- 0.00 - 1.00
    
    -- 状态
    status TEXT DEFAULT 'completed',        -- pending, processing, completed, failed
    error_message TEXT,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 索引优化
    date_partition DATE GENERATED ALWAYS AS (DATE(created_at)) STORED
);

-- 索引
CREATE INDEX idx_interpretations_domain ON domain_interpretations(domain_id);
CREATE INDEX idx_interpretations_channel ON domain_interpretations(channel_id);
CREATE INDEX idx_interpretations_hash ON domain_interpretations(content_hash);
CREATE INDEX idx_interpretations_date ON domain_interpretations(date_partition);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 领域实体表 (从解读中提取的实体)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS domain_entities (
    id SERIAL PRIMARY KEY,
    
    -- 关联解读
    interpretation_id INTEGER REFERENCES domain_interpretations(id) ON DELETE CASCADE,
    
    -- 实体信息
    domain_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,              -- tiangan, dizhi, wuxing, etc.
    entity_value TEXT NOT NULL,             -- 甲, 子, 木, etc.
    
    -- 属性 (JSON)
    attributes JSONB,
    
    -- 位置信息 (在原始内容中的位置)
    source_region TEXT,                     -- 区域 ID
    source_text TEXT,                       -- 原文
    bbox JSONB,                             -- [x1, y1, x2, y2]
    
    -- 置信度
    confidence DECIMAL(3, 2),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entities_interpretation ON domain_entities(interpretation_id);
CREATE INDEX idx_entities_type ON domain_entities(domain_id, entity_type);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 领域关系表 (实体间关系)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS domain_relations (
    id SERIAL PRIMARY KEY,
    
    -- 关联解读
    interpretation_id INTEGER REFERENCES domain_interpretations(id) ON DELETE CASCADE,
    
    -- 关系信息
    domain_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,            -- sheng, ke, etc.
    
    -- 源和目标实体
    source_entity_id INTEGER REFERENCES domain_entities(id),
    target_entity_id INTEGER REFERENCES domain_entities(id),
    
    -- 属性 (JSON)
    properties JSONB,
    
    -- 置信度
    confidence DECIMAL(3, 2),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_relations_interpretation ON domain_relations(interpretation_id);
CREATE INDEX idx_relations_type ON domain_relations(domain_id, relation_type);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 领域知识库缓存表
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS domain_knowledge_cache (
    id SERIAL PRIMARY KEY,
    
    domain_id TEXT NOT NULL,
    knowledge_type TEXT NOT NULL,           -- entity_def, relation_def, rule
    knowledge_key TEXT NOT NULL,            -- 如 "tiangan.甲"
    
    -- 知识内容 (JSON)
    content JSONB NOT NULL,
    
    -- 来源
    source_file TEXT,                       -- 来源文件路径
    
    -- 版本控制
    version TEXT,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(domain_id, knowledge_type, knowledge_key)
);

CREATE INDEX idx_knowledge_domain ON domain_knowledge_cache(domain_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- 视图: 领域解读统计
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW domain_interpretation_stats AS
SELECT 
    domain_id,
    date_partition AS date,
    COUNT(*) AS interpretation_count,
    AVG(total_latency_ms) AS avg_latency_ms,
    AVG(confidence_score) AS avg_confidence,
    SUM(total_cost_usd) AS total_cost,
    SUM(entities_count) AS total_entities,
    SUM(relations_count) AS total_relations,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS success_rate
FROM domain_interpretations
GROUP BY domain_id, date_partition;
```

### 2.1.9 Phase 2.1 交付物清单

```yaml
交付物:
  文档:
    - docs/tech/vision_module_analysis.md       # vision 模块分析
    - docs/tech/retrieval_module_analysis.md    # retrieval 模块分析
    - docs/tech/ingestion_module_analysis.md    # ingestion 模块分析
    - docs/tech/domain_layer_architecture.md    # 领域层架构设计
    - docs/tech/base_interpreter_spec.md        # 解读器接口规范
    - docs/tech/ontology_schema_spec.md         # 本体 Schema 规范
  
  代码:
    - scripts/analyze_vision_module.py          # 分析脚本
    - scripts/analyze_retrieval_module.py
    - core/storage/migrations/002_domain_infrastructure.sql  # 数据库迁移
  
  图表:
    - docs/diagrams/domain_layer_class.mmd      # 类图 (Mermaid)
    - docs/diagrams/interpretation_flow.mmd     # 解读流程图
    - docs/diagrams/ontology_structure.mmd      # 本体结构图

验收标准:
  - [ ] 完成 core/vision/, core/retrieval/, core/ingestion/ 分析报告
  - [ ] 领域抽象层架构设计通过评审
  - [ ] BaseDomainInterpreter 接口定义完整
  - [ ] OntologySchema 规范文档完成
  - [ ] 数据库迁移脚本可执行
  - [ ] 现有模块扩展点明确标识
```

---

## � Phase 2.2: 共同模块实现 (Day 4-7)

### 2.2.0 目标

实现 `core/domains/` 模块的共同能力，为所有垂直领域提供统一的基础设施。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 2.2: COMMON MODULE IMPLEMENTATION                  │
│                        "先共同，后差分"                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Phase 2.2 分为 3 个部分:                                                   │
│                                                                              │
│   Part 1 (本节): 基础类型 + 模块入口 + 基类定义                              │
│   ├── core/domains/__init__.py          # 模块入口                          │
│   ├── core/domains/types.py             # 数据类型定义                       │
│   ├── core/domains/exceptions.py        # 异常定义                          │
│   └── core/domains/base_interpreter.py  # 基类 (Part 1/2)                   │
│                                                                              │
│   Part 2: 基类完成 + 注册器                                                  │
│   ├── core/domains/base_interpreter.py  # 基类 (Part 2/2)                   │
│   └── core/domains/registry.py          # 领域注册器                         │
│                                                                              │
│   Part 3: 本体 Schema + 叙事引擎 + 测试                                      │
│   ├── core/domains/ontology_schema.py   # 本体验证器                         │
│   ├── core/domains/narrative_engine.py  # 叙事引擎                           │
│   └── tests/core/domains/               # 单元测试                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2.1 实现 core/domains/types.py - 数据类型定义

#### 设计原则

```yaml
类型设计原则:
  1. 使用 dataclass 定义所有数据结构
  2. 支持 JSON 序列化/反序列化
  3. 类型注解完整，支持静态检查
  4. 与数据库 Schema 对齐 (Phase 2.1.8)
  5. 可扩展性：领域可添加自定义属性
```

#### 完整实现

```python
# core/domains/types.py
"""
领域解读数据类型定义

设计原则:
1. 所有核心数据结构使用 dataclass
2. 支持 JSON 序列化用于数据库存储
3. 类型注解完整，支持 IDE 和静态检查
4. 与 Phase 2.1.8 数据库 Schema 对齐
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from abc import ABC


# ═══════════════════════════════════════════════════════════════════════════════
# 枚举类型
# ═══════════════════════════════════════════════════════════════════════════════

class ContentType(Enum):
    """内容类型"""
    IMAGE = "image"
    TEXT = "text"
    PDF_PAGE = "pdf_page"
    AUDIO = "audio"  # 预留
    VIDEO = "video"  # 预留


class InterpretationStatus(Enum):
    """解读状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class InterpretationDepth(Enum):
    """解读深度"""
    SURFACE = "surface"      # 表层 - 快速
    STANDARD = "standard"    # 标准
    DEEP = "deep"            # 深度
    EXHAUSTIVE = "exhaustive"  # 穷尽式 - 最慢


# ═══════════════════════════════════════════════════════════════════════════════
# 基础数据类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BoundingBox:
    """边界框"""
    x1: float
    y1: float
    x2: float
    y2: float
    
    @property
    def width(self) -> float:
        return self.x2 - self.x1
    
    @property
    def height(self) -> float:
        return self.y2 - self.y1
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)
    
    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]
    
    @classmethod
    def from_list(cls, bbox: List[float]) -> "BoundingBox":
        return cls(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3])


@dataclass
class GPURequirements:
    """GPU 资源需求"""
    min_vram_gb: int = 8
    recommended_vram_gb: int = 24
    reason: str = ""
    
    def can_run_on(self, available_vram_gb: int) -> bool:
        """检查是否可以在给定显存上运行"""
        return available_vram_gb >= self.min_vram_gb


# ═══════════════════════════════════════════════════════════════════════════════
# 输入类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ContentInput:
    """
    内容输入
    
    统一的输入格式，支持图像、文本、PDF 页面等
    """
    type: ContentType
    data: Union[bytes, str]  # 图像为 bytes，文本为 str
    
    # 可选上下文
    context: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    filename: Optional[str] = None
    page_number: Optional[int] = None  # PDF 页码
    
    # 关联信息
    channel_id: Optional[str] = None
    document_id: Optional[str] = None
    
    def __post_init__(self):
        """验证输入"""
        if self.type == ContentType.IMAGE and not isinstance(self.data, bytes):
            raise ValueError("Image content must be bytes")
        if self.type == ContentType.TEXT and not isinstance(self.data, str):
            raise ValueError("Text content must be str")
    
    @property
    def size_bytes(self) -> int:
        """获取内容大小"""
        if isinstance(self.data, bytes):
            return len(self.data)
        return len(self.data.encode('utf-8'))
    
    def get_hash(self) -> str:
        """获取内容哈希，用于缓存"""
        import hashlib
        if isinstance(self.data, bytes):
            return hashlib.sha256(self.data).hexdigest()
        return hashlib.sha256(self.data.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# 分解结果类型 (Decomposition)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Region:
    """
    检测到的区域
    
    表示图像/文档中的一个语义区域
    """
    id: str                              # 区域 ID
    type: str                            # 区域类型: title, text, image, table, dialog_bubble, etc.
    bbox: BoundingBox                    # 边界框
    confidence: float = 1.0              # 检测置信度
    
    # 区域内容
    content: Optional[str] = None        # OCR 提取的文本
    
    # 领域特有属性 (可扩展)
    domain_attributes: Dict[str, Any] = field(default_factory=dict)
    
    # 层级关系
    parent_id: Optional[str] = None      # 父区域 ID
    children_ids: List[str] = field(default_factory=list)


@dataclass
class VisualElement:
    """
    视觉元素
    
    表示图像中检测到的视觉符号、图标等
    """
    id: str
    type: str                            # 元素类型: character, symbol, icon, etc.
    bbox: Optional[BoundingBox] = None
    confidence: float = 1.0
    
    # 元素描述
    description: Optional[str] = None
    
    # 领域特有属性
    domain_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecompositionResult:
    """
    分解结果
    
    decompose() 方法的返回值
    """
    # 检测到的区域
    regions: List[Region] = field(default_factory=list)
    
    # OCR 提取的文本 (按区域分组)
    texts: Dict[str, str] = field(default_factory=dict)  # region_id -> text
    
    # 视觉元素
    visual_elements: List[VisualElement] = field(default_factory=list)
    
    # 全局文本 (所有文本合并)
    full_text: str = ""
    
    # 处理元数据
    processing_time_ms: int = 0
    model_used: str = ""
    
    # 原始 VLM 响应 (用于调试)
    raw_response: Optional[Dict[str, Any]] = None
    
    def get_region_by_id(self, region_id: str) -> Optional[Region]:
        """通过 ID 获取区域"""
        for region in self.regions:
            if region.id == region_id:
                return region
        return None
    
    def get_regions_by_type(self, region_type: str) -> List[Region]:
        """获取指定类型的所有区域"""
        return [r for r in self.regions if r.type == region_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于数据库存储"""
        return {
            "regions": [asdict(r) for r in self.regions],
            "texts": self.texts,
            "visual_elements": [asdict(v) for v in self.visual_elements],
            "full_text": self.full_text,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 语义理解结果类型 (Semantic Understanding)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Entity:
    """
    识别的实体
    
    表示从内容中提取的领域实体
    """
    id: str                              # 实体 ID
    type: str                            # 实体类型 (来自本体定义)
    value: str                           # 实体值
    
    # 属性
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # 来源追溯
    source_region_id: Optional[str] = None   # 来源区域
    source_text: Optional[str] = None        # 原文
    bbox: Optional[BoundingBox] = None       # 位置
    
    # 置信度
    confidence: float = 1.0
    
    # 知识库链接
    knowledge_id: Optional[str] = None       # 链接到知识库条目


@dataclass
class Relation:
    """
    实体关系
    
    表示实体之间的关系
    """
    id: str
    type: str                            # 关系类型 (来自本体定义)
    
    # 源和目标
    source_entity_id: str
    target_entity_id: str
    
    # 属性
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # 置信度
    confidence: float = 1.0
    
    # 推理依据
    evidence: Optional[str] = None


@dataclass
class SemanticResult:
    """
    语义理解结果
    
    understand() 方法的返回值
    """
    # 识别的实体
    entities: List[Entity] = field(default_factory=list)
    
    # 实体关系
    relations: List[Relation] = field(default_factory=list)
    
    # 全局属性
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # 处理元数据
    processing_time_ms: int = 0
    model_used: str = ""
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """通过 ID 获取实体"""
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        return None
    
    def get_entities_by_type(self, entity_type: str) -> List[Entity]:
        """获取指定类型的所有实体"""
        return [e for e in self.entities if e.type == entity_type]
    
    def get_relations_for_entity(self, entity_id: str) -> List[Relation]:
        """获取与实体相关的所有关系"""
        return [
            r for r in self.relations 
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entities": [asdict(e) for e in self.entities],
            "relations": [asdict(r) for r in self.relations],
            "attributes": self.attributes,
            "processing_time_ms": self.processing_time_ms,
            "model_used": self.model_used,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 叙事重构结果类型 (Narrative Reconstruction)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class KnowledgePoint:
    """知识点"""
    id: str
    title: str
    content: str
    category: str = ""
    importance: int = 1  # 1-5
    source_entities: List[str] = field(default_factory=list)  # 关联的实体 ID


@dataclass
class NarrativeResult:
    """
    叙事重构结果
    
    reconstruct_narrative() 方法的返回值
    """
    # 一句话摘要
    summary: str = ""
    
    # 完整解读文本
    detailed_interpretation: str = ""
    
    # 知识点列表
    knowledge_points: List[KnowledgePoint] = field(default_factory=list)
    
    # 叙事类型
    narrative_type: str = ""  # 来自 narrative_schema
    
    # 艺术风格 (图像)
    art_style: Optional[str] = None
    
    # 情感基调
    emotional_tone: Optional[str] = None
    
    # 置信度
    confidence: float = 1.0
    
    # 处理元数据
    processing_time_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "summary": self.summary,
            "detailed_interpretation": self.detailed_interpretation,
            "knowledge_points": [asdict(kp) for kp in self.knowledge_points],
            "narrative_type": self.narrative_type,
            "art_style": self.art_style,
            "emotional_tone": self.emotional_tone,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 完整解读结果类型 (Full Interpretation)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InterpretationMetadata:
    """解读元数据"""
    # 请求信息
    request_id: str
    domain_id: str
    content_type: ContentType
    content_hash: str
    
    # 时间信息
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # 性能指标
    total_latency_ms: int = 0
    decompose_latency_ms: int = 0
    understand_latency_ms: int = 0
    narrative_latency_ms: int = 0
    
    # 成本 (关联 Phase 1)
    total_cost_usd: float = 0.0
    
    # 模型信息
    models_used: Dict[str, str] = field(default_factory=dict)
    
    # 状态
    status: InterpretationStatus = InterpretationStatus.PENDING
    error_message: Optional[str] = None
    
    # 缓存
    cached: bool = False


@dataclass
class InterpretationResult:
    """
    完整解读结果
    
    interpret() 方法的返回值，聚合所有阶段的结果
    """
    # 三阶段结果
    decomposition: DecompositionResult
    semantics: SemanticResult
    narrative: NarrativeResult
    
    # 元数据
    metadata: InterpretationMetadata
    
    # 统计信息
    @property
    def entities_count(self) -> int:
        return len(self.semantics.entities)
    
    @property
    def relations_count(self) -> int:
        return len(self.semantics.relations)
    
    @property
    def confidence_score(self) -> float:
        """综合置信度"""
        scores = [
            self.narrative.confidence,
            *[e.confidence for e in self.semantics.entities],
            *[r.confidence for r in self.semantics.relations],
        ]
        return sum(scores) / len(scores) if scores else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于数据库存储"""
        return {
            "decomposition": self.decomposition.to_dict(),
            "semantics": self.semantics.to_dict(),
            "narrative": self.narrative.to_dict(),
            "metadata": {
                "request_id": self.metadata.request_id,
                "domain_id": self.metadata.domain_id,
                "content_type": self.metadata.content_type.value,
                "content_hash": self.metadata.content_hash,
                "total_latency_ms": self.metadata.total_latency_ms,
                "total_cost_usd": self.metadata.total_cost_usd,
                "status": self.metadata.status.value,
                "cached": self.metadata.cached,
            },
            "entities_count": self.entities_count,
            "relations_count": self.relations_count,
            "confidence_score": self.confidence_score,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# 验证结果类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


# ═══════════════════════════════════════════════════════════════════════════════
# 领域信息类型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DomainInfo:
    """领域信息 (用于注册表)"""
    domain_id: str
    domain_name: str
    domain_name_en: str
    description: str
    
    # 能力
    supported_content_types: List[ContentType]
    
    # GPU 需求
    gpu_requirements: GPURequirements
    
    # 状态
    enabled: bool = True
    
    # 版本
    version: str = "1.0.0"
    
    # 统计
    interpretation_count: int = 0
    avg_latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷工厂函数
# ═══════════════════════════════════════════════════════════════════════════════

def create_image_input(
    image_bytes: bytes,
    channel_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ContentInput:
    """创建图像输入"""
    return ContentInput(
        type=ContentType.IMAGE,
        data=image_bytes,
        channel_id=channel_id,
        context=context or {}
    )


def create_text_input(
    text: str,
    channel_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> ContentInput:
    """创建文本输入"""
    return ContentInput(
        type=ContentType.TEXT,
        data=text,
        channel_id=channel_id,
        context=context or {}
    )
```

### 2.2.2 实现 core/domains/exceptions.py - 异常定义

#### 完整实现

```python
# core/domains/exceptions.py
"""
领域模块异常定义

设计原则:
1. 异常层级清晰
2. 包含足够的上下文信息
3. 支持异常链
4. 与 HTTP 状态码对应
"""

from typing import Any, Dict, Optional


class DomainError(Exception):
    """
    领域模块基础异常
    
    所有领域相关异常的基类
    """
    
    def __init__(
        self,
        message: str,
        domain_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.domain_id = domain_id
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 API 响应"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "domain_id": self.domain_id,
            "details": self.details,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 注册相关异常
# ═══════════════════════════════════════════════════════════════════════════════

class DomainNotFoundError(DomainError):
    """领域未找到"""
    
    def __init__(self, domain_id: str):
        super().__init__(
            message=f"Domain not found: {domain_id}",
            domain_id=domain_id
        )


class DomainAlreadyExistsError(DomainError):
    """领域已存在"""
    
    def __init__(self, domain_id: str):
        super().__init__(
            message=f"Domain already exists: {domain_id}",
            domain_id=domain_id
        )


class DomainDisabledError(DomainError):
    """领域已禁用"""
    
    def __init__(self, domain_id: str):
        super().__init__(
            message=f"Domain is disabled: {domain_id}",
            domain_id=domain_id
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 本体相关异常
# ═══════════════════════════════════════════════════════════════════════════════

class OntologyError(DomainError):
    """本体相关异常基类"""
    pass


class OntologyLoadError(OntologyError):
    """本体加载失败"""
    
    def __init__(self, domain_id: str, path: str, cause: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to load ontology for domain '{domain_id}' from '{path}'",
            domain_id=domain_id,
            details={"path": path},
            cause=cause
        )


class OntologyValidationError(OntologyError):
    """本体验证失败"""
    
    def __init__(self, domain_id: str, errors: list):
        super().__init__(
            message=f"Ontology validation failed for domain '{domain_id}'",
            domain_id=domain_id,
            details={"errors": errors}
        )


class EntityTypeNotFoundError(OntologyError):
    """实体类型未定义"""
    
    def __init__(self, domain_id: str, entity_type: str):
        super().__init__(
            message=f"Entity type '{entity_type}' not found in domain '{domain_id}'",
            domain_id=domain_id,
            details={"entity_type": entity_type}
        )


class RelationTypeNotFoundError(OntologyError):
    """关系类型未定义"""
    
    def __init__(self, domain_id: str, relation_type: str):
        super().__init__(
            message=f"Relation type '{relation_type}' not found in domain '{domain_id}'",
            domain_id=domain_id,
            details={"relation_type": relation_type}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 解读相关异常
# ═══════════════════════════════════════════════════════════════════════════════

class InterpretationError(DomainError):
    """解读相关异常基类"""
    pass


class InvalidInputError(InterpretationError):
    """无效输入"""
    
    def __init__(self, domain_id: str, reason: str):
        super().__init__(
            message=f"Invalid input for domain '{domain_id}': {reason}",
            domain_id=domain_id,
            details={"reason": reason}
        )


class ContentTypeNotSupportedError(InterpretationError):
    """内容类型不支持"""
    
    def __init__(self, domain_id: str, content_type: str, supported_types: list):
        super().__init__(
            message=f"Content type '{content_type}' not supported by domain '{domain_id}'",
            domain_id=domain_id,
            details={
                "content_type": content_type,
                "supported_types": supported_types
            }
        )


class DecompositionError(InterpretationError):
    """分解阶段失败"""
    
    def __init__(self, domain_id: str, reason: str, cause: Optional[Exception] = None):
        super().__init__(
            message=f"Decomposition failed for domain '{domain_id}': {reason}",
            domain_id=domain_id,
            details={"reason": reason, "stage": "decompose"},
            cause=cause
        )


class SemanticUnderstandingError(InterpretationError):
    """语义理解阶段失败"""
    
    def __init__(self, domain_id: str, reason: str, cause: Optional[Exception] = None):
        super().__init__(
            message=f"Semantic understanding failed for domain '{domain_id}': {reason}",
            domain_id=domain_id,
            details={"reason": reason, "stage": "understand"},
            cause=cause
        )


class NarrativeReconstructionError(InterpretationError):
    """叙事重构阶段失败"""
    
    def __init__(self, domain_id: str, reason: str, cause: Optional[Exception] = None):
        super().__init__(
            message=f"Narrative reconstruction failed for domain '{domain_id}': {reason}",
            domain_id=domain_id,
            details={"reason": reason, "stage": "narrative"},
            cause=cause
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 资源相关异常
# ═══════════════════════════════════════════════════════════════════════════════

class ResourceError(DomainError):
    """资源相关异常基类"""
    pass


class InsufficientGPUMemoryError(ResourceError):
    """GPU 显存不足"""
    
    def __init__(
        self, 
        domain_id: str, 
        required_gb: int, 
        available_gb: int
    ):
        super().__init__(
            message=f"Insufficient GPU memory for domain '{domain_id}': "
                    f"required {required_gb}GB, available {available_gb}GB",
            domain_id=domain_id,
            details={
                "required_gb": required_gb,
                "available_gb": available_gb
            }
        )


class BudgetExceededError(ResourceError):
    """预算超限"""
    
    def __init__(
        self, 
        domain_id: str, 
        estimated_cost: float, 
        remaining_budget: float
    ):
        super().__init__(
            message=f"Budget exceeded for domain '{domain_id}': "
                    f"estimated ${estimated_cost:.4f}, remaining ${remaining_budget:.4f}",
            domain_id=domain_id,
            details={
                "estimated_cost": estimated_cost,
                "remaining_budget": remaining_budget
            }
        )


class KnowledgeBaseNotFoundError(ResourceError):
    """知识库未找到"""
    
    def __init__(self, domain_id: str, knowledge_type: str):
        super().__init__(
            message=f"Knowledge base '{knowledge_type}' not found for domain '{domain_id}'",
            domain_id=domain_id,
            details={"knowledge_type": knowledge_type}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 配置相关异常
# ═══════════════════════════════════════════════════════════════════════════════

class ConfigurationError(DomainError):
    """配置相关异常"""
    
    def __init__(self, domain_id: str, config_key: str, reason: str):
        super().__init__(
            message=f"Configuration error for domain '{domain_id}': "
                    f"key '{config_key}' - {reason}",
            domain_id=domain_id,
            details={"config_key": config_key, "reason": reason}
        )
```

### 2.2.3 实现 core/domains/__init__.py - 模块入口

#### 完整实现

```python
# core/domains/__init__.py
"""
OmniRAG 垂直领域模块

本模块提供垂直领域深度解读能力的基础设施：
- 领域注册与发现
- 统一的解读器接口
- 本体 Schema 定义与验证
- 叙事重构引擎

设计原则：
1. 共同能力在此模块根目录
2. 领域差分实现在子目录 (metaphysics/, comic/, ...)
3. 所有领域必须继承 BaseDomainInterpreter
4. 与 Phase 1 算力层无缝集成

使用示例：
    # 注册领域
    from core.domains import DomainRegistry
    registry = DomainRegistry()
    registry.register("metaphysics_chinese", MetaphysicsInterpreter)
    
    # 执行解读
    interpreter = registry.get("metaphysics_chinese")
    result = await interpreter.interpret(content_input)
    
    # 便捷函数
    from core.domains import interpret_document
    result = await interpret_document(image_bytes, domain_id="metaphysics_chinese")
"""

from core.domains.types import (
    # 枚举
    ContentType,
    InterpretationStatus,
    InterpretationDepth,
    
    # 基础类型
    BoundingBox,
    GPURequirements,
    
    # 输入
    ContentInput,
    create_image_input,
    create_text_input,
    
    # 分解结果
    Region,
    VisualElement,
    DecompositionResult,
    
    # 语义结果
    Entity,
    Relation,
    SemanticResult,
    
    # 叙事结果
    KnowledgePoint,
    NarrativeResult,
    
    # 完整结果
    InterpretationMetadata,
    InterpretationResult,
    
    # 验证
    ValidationResult,
    
    # 领域信息
    DomainInfo,
)

from core.domains.exceptions import (
    # 基础异常
    DomainError,
    
    # 注册异常
    DomainNotFoundError,
    DomainAlreadyExistsError,
    DomainDisabledError,
    
    # 本体异常
    OntologyError,
    OntologyLoadError,
    OntologyValidationError,
    EntityTypeNotFoundError,
    RelationTypeNotFoundError,
    
    # 解读异常
    InterpretationError,
    InvalidInputError,
    ContentTypeNotSupportedError,
    DecompositionError,
    SemanticUnderstandingError,
    NarrativeReconstructionError,
    
    # 资源异常
    ResourceError,
    InsufficientGPUMemoryError,
    BudgetExceededError,
    KnowledgeBaseNotFoundError,
    
    # 配置异常
    ConfigurationError,
)

# 延迟导入，避免循环依赖
# 这些将在各自模块实现后取消注释

# from core.domains.base_interpreter import BaseDomainInterpreter
# from core.domains.registry import DomainRegistry, get_domain_registry
# from core.domains.ontology_schema import OntologySchema
# from core.domains.narrative_engine import NarrativeEngine


__all__ = [
    # ─────────────────────────────────────────────────────────────
    # 枚举类型
    # ─────────────────────────────────────────────────────────────
    "ContentType",
    "InterpretationStatus",
    "InterpretationDepth",
    
    # ─────────────────────────────────────────────────────────────
    # 数据类型
    # ─────────────────────────────────────────────────────────────
    "BoundingBox",
    "GPURequirements",
    "ContentInput",
    "Region",
    "VisualElement",
    "DecompositionResult",
    "Entity",
    "Relation",
    "SemanticResult",
    "KnowledgePoint",
    "NarrativeResult",
    "InterpretationMetadata",
    "InterpretationResult",
    "ValidationResult",
    "DomainInfo",
    
    # ─────────────────────────────────────────────────────────────
    # 工厂函数
    # ─────────────────────────────────────────────────────────────
    "create_image_input",
    "create_text_input",
    
    # ─────────────────────────────────────────────────────────────
    # 异常
    # ─────────────────────────────────────────────────────────────
    "DomainError",
    "DomainNotFoundError",
    "DomainAlreadyExistsError",
    "DomainDisabledError",
    "OntologyError",
    "OntologyLoadError",
    "OntologyValidationError",
    "EntityTypeNotFoundError",
    "RelationTypeNotFoundError",
    "InterpretationError",
    "InvalidInputError",
    "ContentTypeNotSupportedError",
    "DecompositionError",
    "SemanticUnderstandingError",
    "NarrativeReconstructionError",
    "ResourceError",
    "InsufficientGPUMemoryError",
    "BudgetExceededError",
    "KnowledgeBaseNotFoundError",
    "ConfigurationError",
    
    # ─────────────────────────────────────────────────────────────
    # 核心类 (实现后取消注释)
    # ─────────────────────────────────────────────────────────────
    # "BaseDomainInterpreter",
    # "DomainRegistry",
    # "get_domain_registry",
    # "OntologySchema",
    # "NarrativeEngine",
]


# 版本信息
__version__ = "0.1.0"
__author__ = "OmniRAG Team"


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷函数 (将在完整实现后启用)
# ═══════════════════════════════════════════════════════════════════════════════

async def interpret_document(
    content: bytes | str,
    domain_id: str,
    content_type: ContentType = ContentType.IMAGE,
    depth: InterpretationDepth = InterpretationDepth.STANDARD,
    channel_id: str | None = None,
    **kwargs
) -> InterpretationResult:
    """
    便捷解读函数
    
    提供一站式的文档解读能力，内部处理领域选择、资源分配等。
    
    Args:
        content: 图像字节或文本内容
        domain_id: 领域 ID
        content_type: 内容类型
        depth: 解读深度
        channel_id: Channel ID (用于成本追踪)
        **kwargs: 传递给解读器的额外参数
    
    Returns:
        InterpretationResult: 完整解读结果
    
    Raises:
        DomainNotFoundError: 领域不存在
        ContentTypeNotSupportedError: 内容类型不支持
        BudgetExceededError: 预算超限
    
    Example:
        >>> result = await interpret_document(
        ...     content=image_bytes,
        ...     domain_id="metaphysics_chinese",
        ...     depth=InterpretationDepth.DEEP
        ... )
        >>> print(result.narrative.summary)
    """
    # TODO: 实现后取消注释
    # from core.domains.registry import get_domain_registry
    # 
    # registry = get_domain_registry()
    # interpreter = registry.get(domain_id)
    # 
    # input_data = ContentInput(
    #     type=content_type,
    #     data=content,
    #     channel_id=channel_id,
    #     context={"depth": depth.value, **kwargs}
    # )
    # 
    # return await interpreter.interpret(input_data)
    
    raise NotImplementedError("interpret_document will be implemented in Phase 2.2 Part 2")


def list_available_domains() -> list[DomainInfo]:
    """
    列出所有可用领域
    
    Returns:
        领域信息列表
    
    Example:
        >>> domains = list_available_domains()
        >>> for d in domains:
        ...     print(f"{d.domain_id}: {d.domain_name}")
    """
    # TODO: 实现后取消注释
    # from core.domains.registry import get_domain_registry
    # return get_domain_registry().list_domains()
    
    raise NotImplementedError("list_available_domains will be implemented in Phase 2.2 Part 2")


def get_domain_info(domain_id: str) -> DomainInfo:
    """
    获取领域详情
    
    Args:
        domain_id: 领域 ID
    
    Returns:
        领域信息
    
    Raises:
        DomainNotFoundError: 领域不存在
    """
    # TODO: 实现后取消注释
    # from core.domains.registry import get_domain_registry
    # return get_domain_registry().get_info(domain_id)
    
    raise NotImplementedError("get_domain_info will be implemented in Phase 2.2 Part 2")
```

### 2.2.4 Phase 2.2 Part 1 交付物清单

```yaml
交付物:
  代码文件:
    - core/domains/__init__.py           # 模块入口
    - core/domains/types.py              # 数据类型定义
    - core/domains/exceptions.py         # 异常定义
  
  测试文件:
    - tests/core/domains/test_types.py   # 类型测试
    - tests/core/domains/test_exceptions.py  # 异常测试

验收标准:
  - [ ] 所有数据类型可正确实例化
  - [ ] 数据类型支持 JSON 序列化
  - [ ] 异常层级清晰，包含足够上下文
  - [ ] 类型注解完整，mypy 检查通过
  - [ ] 与 Phase 2.1.8 数据库 Schema 对齐

单元测试示例:
  ```python
  # tests/core/domains/test_types.py
  
  import pytest
  from core.domains.types import (
      ContentInput, ContentType, DecompositionResult,
      Region, BoundingBox, Entity, InterpretationResult
  )
  
  
  class TestContentInput:
      def test_create_image_input(self):
          content = ContentInput(
              type=ContentType.IMAGE,
              data=b"fake_image_bytes"
          )
          assert content.type == ContentType.IMAGE
          assert content.size_bytes == 16
      
      def test_create_text_input(self):
          content = ContentInput(
              type=ContentType.TEXT,
              data="测试文本"
          )
          assert content.type == ContentType.TEXT
      
      def test_image_input_requires_bytes(self):
          with pytest.raises(ValueError):
              ContentInput(type=ContentType.IMAGE, data="not bytes")
      
      def test_get_hash(self):
          content = ContentInput(type=ContentType.TEXT, data="test")
          assert len(content.get_hash()) == 64  # SHA256
  
  
  class TestBoundingBox:
      def test_properties(self):
          bbox = BoundingBox(x1=0, y1=0, x2=100, y2=50)
          assert bbox.width == 100
          assert bbox.height == 50
          assert bbox.area == 5000
          assert bbox.center == (50, 25)
      
      def test_to_list(self):
          bbox = BoundingBox(x1=10, y1=20, x2=30, y2=40)
          assert bbox.to_list() == [10, 20, 30, 40]
      
      def test_from_list(self):
          bbox = BoundingBox.from_list([10, 20, 30, 40])
          assert bbox.x1 == 10
          assert bbox.y2 == 40
  
  
  class TestDecompositionResult:
      def test_to_dict(self):
          result = DecompositionResult(
              regions=[
                  Region(id="r1", type="text", bbox=BoundingBox(0,0,100,100))
              ],
              texts={"r1": "Hello"},
              full_text="Hello"
          )
          
          d = result.to_dict()
          assert "regions" in d
          assert len(d["regions"]) == 1
      
      def test_get_region_by_id(self):
          r1 = Region(id="r1", type="text", bbox=BoundingBox(0,0,100,100))
          result = DecompositionResult(regions=[r1])
          
          assert result.get_region_by_id("r1") == r1
          assert result.get_region_by_id("r2") is None
  ```
```

---

## 🔜 Phase 2.2 Part 2 预告

**下一节内容: 基类完成 + 注册器**

- 实现 `core/domains/base_interpreter.py` - 基类完整实现
  - 抽象方法定义
  - 生命周期管理
  - 与算力层集成
  - 成本追踪集成
- 实现 `core/domains/registry.py` - 领域注册器
  - 注册/发现机制
  - 自动领域检测
  - 单例模式

---

*Phase 2.2 Part 1 开发指南 v1.0 | 2025-12-14 | OmniRAG Team*
