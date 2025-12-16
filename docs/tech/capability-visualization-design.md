# Core 能力可视化设计方案

> **版本**: v1.0 | **创建日期**: 2025-12-15
> **目标**: 将 core 中的核心能力可视化，变为用户可以配置、操作、选择、使用的资产

---

## 一、现状分析

### 1.1 Core 的能力资产（已实现）

| 类别 | 能力 | 状态 |
|------|------|------|
| **Ingestion Pipeline** | Loader → Router → Parser → Chunker → Embedder → Indexer | ✅ 完整 |
| **Retrieval Pipeline** | Preprocessor → Retriever → Reranker → Generator | ✅ 完整 |
| **高级算法** | RAPTOR, GraphRAG, MindMap (Light/Deep) | ✅ 完整 |
| **LLM Gateway** | 路由策略, 熔断降级, 成本追踪 | ✅ 完整 |
| **垂直领域** | Comic, Metaphysics 解读器 | ✅ 完整 |
| **Capabilities** | manifest.yaml 定义了 20+ 能力 | ✅ 完整 |
| **多租户** | Channel-KB-Chat 三层隔离 | ✅ 完整 |

### 1.2 Server 的暴露情况（部分）

| API | 路径 | 状态 |
|-----|------|------|
| 能力清单 | `/api/capabilities/list` | ✅ 已有 |
| 能力分组 | `/api/capabilities/grouped` | ✅ 已有 |
| 能力详情 | `/api/capabilities/detail/{id}` | ✅ 已有 |
| KB 配置 | `/api/kb/{name}/config` | ⚠️ 部分 |
| Ingest 场景 | `/api/ingest/scenarios` | ✅ 已有 |
| 算法执行 | RAPTOR/GraphRAG | ⚠️ 内部调用 |
| 领域注册 | Domain Registry | ❌ 未暴露 |
| LLM 路由策略 | cost_first/balanced | ❌ 未暴露 |

### 1.3 Frontend 的实现情况（落后）

| 页面 | 当前状态 | 问题 |
|------|----------|------|
| `KnowledgeBasesPage` | 基础 CRUD | 缺少能力配置入口 |
| `StrategyConfig` | 硬编码表单 | 未使用 manifest.yaml schema |
| `IngestPage` | 基础上传 | 缺少实时进度、能力选择 |
| `ChatPage` | 基础对话 | 缺少检索策略配置 |
| **缺失** | 能力市场页 | 无 |
| **缺失** | 算法控制台 | 无 |
| **缺失** | 领域管理 | 无 |

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (能力可视化层)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ 能力市场     │  │ KB 配置中心  │  │ 算法控制台   │  │ 领域管理     │    │
│  │ CapStore    │  │ KBConfig     │  │ AlgoConsole │  │ DomainMgr   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Server (能力 API 层)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ capability/  │  │ kb/config    │  │ algo/        │  │ domain/      │    │
│  │ list,detail  │  │ strategies   │  │ raptor,graph │  │ register,run │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Core (能力实现层)                                 │
│  capabilities/   state.py   algorithms/   domains/   llm/   storage/       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、实施方案

### Phase 1: Server API 补全 (Week 1-2)

#### 3.1.1 新增 API 路由

```
server/
├── api/
│   ├── capabilities.py    # 能力 API (扩展现有)
│   ├── kb_config.py       # KB 配置 API (新增)
│   ├── algorithms.py      # 算法 API (新增)
│   ├── domains.py         # 领域 API (新增)
│   └── llm_gateway.py     # LLM 网关 API (新增)
```

#### 3.1.2 关键 API 设计

**KB 配置 API**

```python
# GET /api/kb/{kb_name}/capabilities
# 返回当前 KB 启用的能力列表和配置

# PUT /api/kb/{kb_name}/capabilities
# 批量更新 KB 的能力配置
{
  "capabilities": {
    "basic.chunking": {"enabled": true, "config": {"mode": "semantic", "chunk_size": 600}},
    "enhanced.table_recognition": {"enabled": true, "config": {}},
    "advanced.raptor": {"enabled": false}
  }
}

# GET /api/kb/{kb_name}/strategy
# 返回合并后的完整策略配置
```

**算法 API**

```python
# POST /api/algorithms/raptor/run
{
  "kb_name": "legal_kb",
  "mode": "light",  # or "deep"
  "config": {"max_cluster": 8}
}

# GET /api/algorithms/raptor/{task_id}/status
# SSE 流式返回进度

# POST /api/algorithms/graphrag/run
# POST /api/algorithms/mindmap/run
```

**领域 API**

```python
# GET /api/domains
# 列出所有已注册领域

# GET /api/domains/{domain_id}/ontology
# 获取领域本体 schema

# POST /api/kb/{kb_name}/domain
# 为 KB 指定垂直领域
{"domain_id": "comic", "config": {...}}
```

**LLM Gateway API**

```python
# GET /api/llm/routing-strategies
# 返回可用路由策略: cost_first, performance_first, balanced

# PUT /api/kb/{kb_name}/llm-config
{
  "routing_strategy": "cost_first",
  "budget_limit": 100.0,
  "fallback_chain": ["gpt-4o-mini", "deepseek-chat"]
}
```

---

### Phase 2: Frontend 能力市场 (Week 3-4)

#### 3.2.1 新增页面结构

```
frontend/src/pages/
├── CapabilityStorePage.tsx    # 能力市场
├── KBCapabilityConfig.tsx     # KB 能力配置
├── AlgorithmConsolePage.tsx   # 算法控制台
├── DomainManagerPage.tsx      # 领域管理
└── LLMStrategyPage.tsx        # LLM 策略配置
```

#### 3.2.2 能力市场页面设计

```
┌─────────────────────────────────────────────────────────────┐
│  能力市场                              [搜索能力...]        │
├─────────────────────────────────────────────────────────────┤
│  [基础] [增强] [专业] [高级]                                │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ 📄 文本提取     │  │ ✂️ 文档分块     │  │ 🔢 向量嵌入 │ │
│  │                 │  │                 │  │             │ │
│  │ 从文档提取纯文本│  │ 分块策略可配置  │  │ BGE-M3...   │ │
│  │                 │  │                 │  │             │ │
│  │ [始终启用] ⚙️   │  │ [配置] ⚙️       │  │ [配置] ⚙️   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ 🖼️ OCR识别      │  │ 📊 表格识别     │  │ 🎨 版面分析 │ │
│  │                 │  │                 │  │             │ │
│  │ 多Provider可选  │  │ 支持复杂嵌套表  │  │ GPU推荐     │ │
│  │                 │  │                 │  │             │ │
│  │ [配置] ⚙️       │  │ [配置] ⚙️       │  │ [配置] ⚙️   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2.3 KB 能力配置页面

```
┌─────────────────────────────────────────────────────────────┐
│  知识库: legal_kb                                           │
├─────────────────────────────────────────────────────────────┤
│  [概览] [文档] [能力配置] [算法] [检索测试]                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  已启用能力 (6/15)                      [+ 添加能力]        │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐│
│  │ ✅ 文档分块                                    [配置]  ││
│  │    模式: semantic | 块大小: 600 | 重叠: 60             ││
│  ├────────────────────────────────────────────────────────┤│
│  │ ✅ 表格识别                                    [配置]  ││
│  │    引擎: auto | 置信度阈值: 0.8                        ││
│  ├────────────────────────────────────────────────────────┤│
│  │ ✅ RAPTOR 层次索引                             [配置]  ││
│  │    模式: deep | 最大聚类: 8 | 状态: 已构建             ││
│  └────────────────────────────────────────────────────────┘│
│                                                             │
│  推荐能力 (基于知识库类型)                                  │
│  ┌─────────────────┐  ┌─────────────────┐                  │
│  │ GraphRAG        │  │ PII 过滤        │                  │
│  │ [+ 启用]        │  │ [+ 启用]        │                  │
│  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

#### 3.2.4 动态表单生成

```typescript
// components/DynamicConfigForm.tsx
// 基于 manifest.yaml 的 config_schema 自动生成表单

interface ConfigSchema {
  type: 'object';
  properties: {
    [key: string]: {
      type: string;
      title: string;
      description: string;
      enum?: string[];
      enum_labels?: Record<string, string>;
      minimum?: number;
      maximum?: number;
      default?: any;
      ui_component: 'select' | 'slider' | 'switch' | 'input';
      ui_step?: number;
    };
  };
}

// 根据 ui_component 渲染对应组件
const componentMap = {
  select: SelectField,      // enum + enum_labels
  slider: SliderField,      // min/max/step
  switch: SwitchField,      // boolean
  input: InputField,        // string/number
  multiselect: MultiSelect, // array
};

function DynamicField({ schema, value, onChange }) {
  const Component = componentMap[schema.ui_component];
  return <Component {...schema} value={value} onChange={onChange} />;
}
```

---

### Phase 3: 算法控制台 (Week 5)

```
┌─────────────────────────────────────────────────────────────┐
│  算法控制台                                                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │ RAPTOR 层次摘要                                         ││
│  │                                                          ││
│  │ 目标知识库: [legal_kb ▼]  模式: [Light ○] [Deep ●]     ││
│  │                                                          ││
│  │ 参数配置:                                                ││
│  │ ├─ 最大聚类数: [====●====] 8                            ││
│  │ ├─ 摘要Token: [====●====] 256                           ││
│  │ └─ 使用LLM: [deepseek-chat ▼]                           ││
│  │                                                          ││
│  │ [运行 RAPTOR]                     预估成本: $0.45       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ GraphRAG 知识图谱                                       ││
│  │                                                          ││
│  │ 目标知识库: [legal_kb ▼]  模式: [Light ○] [Deep ●]     ││
│  │                                                          ││
│  │ 参数配置:                                                ││
│  │ ├─ 社区级别: [====●====] 2                              ││
│  │ └─ 实体提取模型: [gpt-4o-mini ▼]                        ││
│  │                                                          ││
│  │ [运行 GraphRAG]                   预估成本: $1.20       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
│  运行历史                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 任务ID      算法     KB        状态    耗时   成本   │  │
│  │ abc123      RAPTOR   legal_kb  ✅完成  2m30s  $0.42  │  │
│  │ def456      GraphRAG paper_kb  🔄运行  1m10s  -      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

### Phase 4: 领域管理 (Week 6)

```
┌─────────────────────────────────────────────────────────────┐
│  垂直领域管理                                               │
├─────────────────────────────────────────────────────────────┤
│  已注册领域                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ 🎨 Comic        │  │ 🔮 Metaphysics  │  │ ➕ 添加领域  │ │
│  │                 │  │                 │  │             │ │
│  │ 漫画/绘本解析   │  │ 玄学/命理解析   │  │             │ │
│  │                 │  │                 │  │             │ │
│  │ [配置] [本体]   │  │ [配置] [本体]   │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  领域本体预览 (Comic)                                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ entities:                                                ││
│  │   - name: Panel                                          ││
│  │     description: 漫画分格                                ││
│  │     attributes: [position, size, reading_order]          ││
│  │   - name: Character                                      ││
│  │     description: 角色                                    ││
│  │     attributes: [name, appearance, emotion]              ││
│  │ relations:                                               ││
│  │   - name: contains                                       ││
│  │     from: Panel                                          ││
│  │     to: Character                                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 四、技术实现要点

### 4.1 能力配置流转

```
                    manifest.yaml
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    Server API Layer                          │
│                                                              │
│  GET /capabilities/list ──► 返回能力卡片数据                 │
│                              ▼                               │
│  GET /capabilities/{id} ──► 返回 config_schema               │
│                              ▼                               │
│  PUT /kb/{kb}/capabilities ─► 合并到 KB 配置                 │
│                              ▼                               │
│  POST /ingest/run ──────────► 读取 KB 配置，注入 State       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                    Core Pipeline                             │
│                                                              │
│  IngestState.strategy_config ──► 各 Node 读取配置执行        │
│  IngestState.capability_loader ─► 按需加载能力实例           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 前端状态管理

```typescript
// store/capabilityStore.ts

interface CapabilityStore {
  // 能力列表缓存
  capabilities: Record<string, Capability>;
  categories: Category[];
  
  // KB 配置
  kbConfigs: Record<string, KBCapabilityConfig>;
  
  // Actions
  fetchCapabilities: () => Promise<void>;
  updateKBCapability: (kb: string, capId: string, config: any) => Promise<void>;
  
  // Derived
  getEnabledCapabilities: (kb: string) => Capability[];
}
```

### 4.3 SSE 进度推送

```typescript
// 算法执行进度监听
function useAlgorithmProgress(taskId: string) {
  const [progress, setProgress] = useState<AlgoProgress>({ stage: 'pending', percent: 0 });
  
  useEffect(() => {
    const es = new EventSource(`/api/algorithms/${taskId}/progress`);
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setProgress(data);
      if (data.stage === 'completed' || data.stage === 'failed') {
        es.close();
      }
    };
    return () => es.close();
  }, [taskId]);
  
  return progress;
}
```

---

## 五、实施优先级

| 阶段 | 内容 | 优先级 | 预估工时 |
|------|------|--------|----------|
| **Phase 1** | Server API 补全 | P0 | 2 weeks |
| **Phase 2** | 能力市场 + KB 配置 | P0 | 2 weeks |
| **Phase 3** | 算法控制台 | P1 | 1 week |
| **Phase 4** | 领域管理 | P2 | 1 week |
| **Phase 5** | LLM 策略配置 | P2 | 0.5 week |

---

## 六、关键依赖

1. **manifest.yaml 完善** - 确保所有能力都有完整的 `config_schema`
2. **capability_routes.py 扩展** - 支持 KB 级别的能力配置 CRUD
3. **前端组件库** - 需要 Slider, MultiSelect 等 UI 组件
4. **SSE 进度推送** - 算法执行需要实时进度反馈

---

## 七、预期收益

| 指标 | 当前 | 目标 |
|------|------|------|
| 能力可见性 | manifest.yaml 内部定义 | UI 卡片展示 |
| 配置方式 | 硬编码/手动 JSON | 可视化表单 |
| 算法执行 | API 调用 | 控制台一键运行 |
| 领域扩展 | 代码级别 | 可视化管理 |

---

## 八、验收标准

### 8.1 Phase 1 验收

- [ ] `/api/kb/{kb_name}/capabilities` GET/PUT 可用
- [ ] `/api/algorithms/raptor/run` POST + SSE 进度可用
- [ ] `/api/domains` GET 返回已注册领域
- [ ] `/api/llm/routing-strategies` GET 返回路由策略

### 8.2 Phase 2 验收

- [ ] 能力市场页面渲染所有能力卡片
- [ ] 分类 Tab 切换正常
- [ ] KB 详情页新增"能力配置" Tab
- [ ] 动态表单根据 schema 正确生成

### 8.3 Phase 3 验收

- [ ] RAPTOR/GraphRAG/MindMap 可从 UI 启动
- [ ] 实时进度条显示
- [ ] 运行历史记录展示

### 8.4 Phase 4 验收

- [ ] 领域列表展示
- [ ] 本体 Schema 预览
- [ ] KB 领域绑定功能

---

## 九、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| manifest.yaml schema 不完整 | 动态表单无法生成 | Phase 0 先审计补全 schema |
| 算法执行时间长 | 用户体验差 | SSE 进度 + 后台任务队列 |
| 前端组件库缺失 | 开发效率低 | 引入 shadcn/ui 或 Ant Design |
| API 向后兼容 | 破坏现有功能 | 新增 /v2/ 路由前缀 |

---

## 十、参考资料

- [core/capabilities/manifest.yaml](../core/capabilities/manifest.yaml) - 能力定义
- [server/capability_routes.py](../server/capability_routes.py) - 现有能力 API
- [docs/architecture.md](./architecture.md) - 系统架构设计
- [core/state.py](../core/state.py) - State 定义
