# Design Document: Capability Visualization System

## Overview

本设计文档描述了 OmniRAG 能力可视化系统的技术架构和实现方案。该系统将 core 中的核心能力（Ingestion Pipeline、Retrieval Pipeline、高级算法、LLM Gateway、垂直领域等）可视化，使其成为用户可以配置、操作、选择、使用的资产。

系统采用三层架构：

1. **Frontend (能力可视化层)**: React + TypeScript 实现的 UI 组件
2. **Server (能力 API 层)**: FastAPI 实现的 RESTful API
3. **Core (能力实现层)**: Python 实现的核心能力模块

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Frontend (能力可视化层)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ CapStore    │  │ KBConfig     │  │ AlgoConsole │  │ DomainMgr   │    │
│  │ 能力市场     │  │ KB 配置中心  │  │ 算法控制台   │  │ 领域管理     │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │            │
│  ┌──────┴─────────────────┴─────────────────┴─────────────────┴──────┐     │
│  │                    Zustand Store (capabilityStore)                │     │
│  └───────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ HTTP/SSE
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Server (能力 API 层)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ capability/  │  │ kb_config/   │  │ algorithms/  │  │ domains/     │    │
│  │ routes.py    │  │ routes.py    │  │ routes.py    │  │ routes.py    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                    │                                        │
│  ┌─────────────────────────────────┴─────────────────────────────────┐     │
│  │                    Task Queue (algorithm execution)               │     │
│  └───────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Core (能力实现层)                                 │
│  capabilities/   state.py   algorithms/   domains/   llm/   storage/       │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### Server API Components

#### 1. KB Config API (`server/api/kb_config.py`)

```python
# API Endpoints
GET  /api/kb/{kb_name}/capabilities      # 获取 KB 启用的能力列表
PUT  /api/kb/{kb_name}/capabilities      # 更新 KB 能力配置
GET  /api/kb/{kb_name}/strategy          # 获取合并后的完整策略

# Request/Response Models
class KBCapabilityConfig(BaseModel):
    capabilities: dict[str, CapabilitySettings]

class CapabilitySettings(BaseModel):
    enabled: bool
    config: dict[str, Any]

class MergedStrategy(BaseModel):
    ingest: IngestStrategyConfig
    retrieval: RetrievalStrategyConfig
    capabilities: dict[str, CapabilitySettings]
```

#### 2. Algorithms API (`server/api/algorithms.py`)

```python
# API Endpoints
POST /api/algorithms/raptor/run          # 启动 RAPTOR 任务
POST /api/algorithms/graphrag/run        # 启动 GraphRAG 任务
POST /api/algorithms/mindmap/run         # 启动 MindMap 任务
GET  /api/algorithms/{task_id}/status    # 获取任务状态
GET  /api/algorithms/{task_id}/progress  # SSE 进度流
GET  /api/algorithms/history             # 获取执行历史

# Request/Response Models
class AlgorithmRunRequest(BaseModel):
    kb_name: str
    mode: str  # "light" | "deep"
    config: dict[str, Any]

class AlgorithmTask(BaseModel):
    task_id: str
    algorithm: str
    kb_name: str
    status: str  # "pending" | "running" | "completed" | "failed"
    progress: int
    stage: str
    created_at: datetime
    completed_at: datetime | None
    error: str | None
    result: dict | None
```

#### 3. Domains API (`server/api/domains.py`)

```python
# API Endpoints
GET  /api/domains                        # 列出所有领域
GET  /api/domains/{domain_id}            # 获取领域详情
GET  /api/domains/{domain_id}/ontology   # 获取领域本体
POST /api/kb/{kb_name}/domain            # 绑定领域到 KB
GET  /api/kb/{kb_name}/domain            # 获取 KB 绑定的领域

# Request/Response Models
class DomainInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    supported_formats: list[str]
    requires: list[str]

class OntologySchema(BaseModel):
    entities: list[EntityDef]
    relations: list[RelationDef]
    attributes: list[AttributeDef]

class DomainBinding(BaseModel):
    domain_id: str
    config: dict[str, Any]
```

#### 4. LLM Gateway API (`server/api/llm_gateway.py`)

```python
# API Endpoints
GET  /api/llm/routing-strategies         # 获取可用路由策略
GET  /api/llm/providers                  # 获取可用 LLM 提供商
PUT  /api/kb/{kb_name}/llm-config        # 更新 KB 的 LLM 配置
GET  /api/kb/{kb_name}/llm-config        # 获取 KB 的 LLM 配置

# Request/Response Models
class RoutingStrategy(BaseModel):
    id: str
    name: str
    description: str

class LLMConfig(BaseModel):
    routing_strategy: str
    budget_limit: float | None
    fallback_chain: list[str]
    provider_configs: dict[str, ProviderConfig]
```

### Frontend Components

#### 1. Capability Store Page (`CapabilityStorePage.tsx`)

```typescript
// 能力市场页面组件
interface CapabilityStorePageProps {}

// 子组件
- CategoryTabs: 分类标签切换
- CapabilityGrid: 能力卡片网格
- CapabilityCard: 单个能力卡片
- SearchBar: 搜索栏
- ConfigModal: 配置弹窗
```

#### 2. KB Capability Config (`KBCapabilityConfig.tsx`)

```typescript
// KB 能力配置组件
interface KBCapabilityConfigProps {
  kbName: string;
}

// 子组件
- EnabledCapabilityList: 已启用能力列表
- AddCapabilityModal: 添加能力弹窗
- CapabilityConfigForm: 能力配置表单
- DependencyStatus: 依赖状态显示
```

#### 3. Dynamic Config Form (`DynamicConfigForm.tsx`)

```typescript
// 动态配置表单组件
interface DynamicConfigFormProps {
  schema: ConfigSchema;
  value: Record<string, any>;
  onChange: (value: Record<string, any>) => void;
  onValidate?: (errors: ValidationError[]) => void;
}

// 字段组件映射
const componentMap = {
  select: SelectField,
  slider: SliderField,
  switch: SwitchField,
  input: InputField,
  "multi-select": MultiSelectField,
  number: NumberField,
  text: TextField,
};
```

#### 4. Algorithm Console (`AlgorithmConsolePage.tsx`)

```typescript
// 算法控制台页面
interface AlgorithmConsolePanelProps {
  algorithm: 'raptor' | 'graphrag' | 'mindmap';
}

// 子组件
- AlgorithmConfigPanel: 算法配置面板
- CostEstimator: 成本估算显示
- ProgressBar: 进度条
- RunHistory: 运行历史表格
```

#### 5. Domain Manager (`DomainManagerPage.tsx`)

```typescript
// 领域管理页面
interface DomainManagerPageProps {}

// 子组件
- DomainCard: 领域卡片
- OntologyViewer: 本体查看器
- DomainBindingModal: 领域绑定弹窗
```

#### 6. LLM Strategy Page (`LLMStrategyPage.tsx`)

```typescript
// LLM 策略配置页面
interface LLMStrategyPageProps {
  kbName: string;
}

// 子组件
- StrategySelector: 策略选择器
- BudgetConfig: 预算配置
- FallbackChainEditor: 降级链编辑器
```

### State Management

```typescript
// store/capabilityStore.ts
interface CapabilityStore {
  // 能力列表缓存
  capabilities: Record<string, Capability>;
  categories: Category[];
  loading: boolean;
  error: string | null;

  // KB 配置
  kbConfigs: Record<string, KBCapabilityConfig>;

  // 算法任务
  algorithmTasks: Record<string, AlgorithmTask>;

  // Actions
  fetchCapabilities: () => Promise<void>;
  fetchKBConfig: (kbName: string) => Promise<void>;
  updateKBCapability: (
    kbName: string,
    capId: string,
    config: any
  ) => Promise<void>;
  enableCapability: (kbName: string, capId: string) => Promise<void>;
  disableCapability: (kbName: string, capId: string) => Promise<void>;
  runAlgorithm: (
    algorithm: string,
    kbName: string,
    config: any
  ) => Promise<string>;
  subscribeToProgress: (
    taskId: string,
    callback: (progress: Progress) => void
  ) => () => void;

  // Selectors
  getEnabledCapabilities: (kbName: string) => Capability[];
  getCapabilitiesByCategory: (category: string) => Capability[];
}
```

## Data Models

### Capability Configuration

```typescript
interface Capability {
  id: string;
  name: string;
  name_en: string;
  description: string;
  description_en: string;
  category: "basic" | "enhanced" | "pro" | "advanced";
  icon: string;
  use_case: string;
  default_enabled: boolean;
  user_configurable: boolean;
  always_on: boolean;
  requires_gpu: boolean;
  gpu_memory_mb: number;
  supported_formats: string[];
  requires: string[];
  config_schema: ConfigSchema | null;
}

interface ConfigSchema {
  type: "object";
  properties: Record<string, PropertySchema>;
  required?: string[];
}

interface PropertySchema {
  type: string;
  title: string;
  description: string;
  enum?: string[];
  enum_labels?: Record<string, string>;
  minimum?: number;
  maximum?: number;
  default?: any;
  ui_component:
    | "select"
    | "slider"
    | "switch"
    | "input"
    | "multi-select"
    | "number"
    | "text";
  ui_step?: number;
  ui_show_if?: {
    field: string;
    value: any;
  };
  available_options?: Array<{ value: string; label: string }>;
}
```

### Algorithm Task

```typescript
interface AlgorithmTask {
  task_id: string;
  algorithm: "raptor" | "graphrag" | "mindmap";
  kb_name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  stage: string;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  result: AlgorithmResult | null;
  estimated_cost: number;
  actual_cost: number | null;
}

interface AlgorithmProgress {
  task_id: string;
  stage: string;
  progress: number;
  message: string;
  timestamp: string;
}
```

### Domain Configuration

```typescript
interface Domain {
  id: string;
  name: string;
  description: string;
  icon: string;
  supported_formats: string[];
  requires: string[];
  ontology: OntologySchema;
}

interface OntologySchema {
  entities: EntityDef[];
  relations: RelationDef[];
}

interface EntityDef {
  name: string;
  description: string;
  attributes: string[];
}

interface RelationDef {
  name: string;
  from: string;
  to: string;
  description: string;
}
```

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees._

### Property 1: KB Capability Configuration Round-Trip

_For any_ KB name and valid capability configuration, saving the configuration via PUT and then retrieving it via GET should return an equivalent configuration.
**Validates: Requirements 1.2, 12.1**

### Property 2: Algorithm Task Creation

_For any_ valid algorithm type (raptor, graphrag, mindmap), KB name, and configuration, starting an algorithm task should return a unique task ID and the task should be retrievable by that ID.
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: SSE Progress Event Structure

_For any_ running algorithm task, progress events emitted via SSE should contain stage (string), progress (0-100), and message (string) fields.
**Validates: Requirements 2.4, 11.2**

### Property 4: Domain Binding Round-Trip

_For any_ KB name and valid domain configuration, binding a domain and then retrieving the binding should return the same domain ID and configuration.
**Validates: Requirements 3.3, 3.4**

### Property 5: LLM Config Round-Trip

_For any_ KB name and valid LLM configuration, updating the config and then retrieving it should return an equivalent configuration.
**Validates: Requirements 4.2, 4.3**

### Property 6: Dynamic Form Component Mapping

_For any_ config_schema property with a ui_component field, the rendered form should contain a component of the corresponding type (select → dropdown, slider → range input, switch → toggle, multi-select → multi-select input).
**Validates: Requirements 7.1, 7.2, 7.3, 7.4**

### Property 7: Conditional Field Visibility

_For any_ config_schema property with ui_show_if condition, the field should be visible only when the referenced field has the specified value.
**Validates: Requirements 7.5**

### Property 8: Capability Search Filtering

_For any_ search query, the filtered capabilities should only include those whose name or description contains the search term (case-insensitive).
**Validates: Requirements 5.5**

### Property 9: Dependency Enforcement

_For any_ capability with dependencies, enabling the capability should fail if any dependency is not satisfied, and the error should list the missing dependencies.
**Validates: Requirements 6.5, 3.5**

### Property 10: Configuration Serialization Round-Trip

_For any_ valid capability configuration, serializing to JSON and deserializing should produce an equivalent configuration that passes schema validation.
**Validates: Requirements 13.1, 13.2**

### Property 11: Algorithm Progress Monotonicity

_For any_ algorithm task, the progress percentage in SSE events should be monotonically non-decreasing (progress never goes backward).
**Validates: Requirements 2.4, 8.4**

### Property 12: Cost Estimation Consistency

_For any_ algorithm configuration and KB, the estimated cost should be a positive number proportional to KB size and algorithm complexity.
**Validates: Requirements 8.2**

### Property 13: Run History Completeness

_For any_ completed or failed algorithm task, the run history should contain an entry with the task's status, duration, and cost.
**Validates: Requirements 8.6**

### Property 14: Ontology Structure Validity

_For any_ domain ontology, all relations should reference entities that exist in the entities list.
**Validates: Requirements 9.5**

### Property 15: Configuration Version History

_For any_ capability configuration update, the system should maintain a version history entry with timestamp and previous value.
**Validates: Requirements 12.3**

## Error Handling

### API Error Responses

```python
class APIError(BaseModel):
    code: str
    message: str
    details: dict | None

# Error codes
CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"
INVALID_CONFIG = "INVALID_CONFIG"
DEPENDENCY_NOT_MET = "DEPENDENCY_NOT_MET"
KB_NOT_FOUND = "KB_NOT_FOUND"
DOMAIN_NOT_FOUND = "DOMAIN_NOT_FOUND"
TASK_NOT_FOUND = "TASK_NOT_FOUND"
ALGORITHM_FAILED = "ALGORITHM_FAILED"
BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
```

### Frontend Error Handling

```typescript
// Error boundary for capability components
class CapabilityErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorDisplay error={this.state.error} />;
    }
    return this.props.children;
  }
}

// API error handling
async function handleAPIError(response: Response) {
  if (!response.ok) {
    const error = await response.json();
    throw new APIError(error.code, error.message, error.details);
  }
}
```

### SSE Error Recovery

```typescript
function useSSEWithRetry(url: string, maxRetries = 3) {
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    const es = new EventSource(url);

    es.onerror = () => {
      if (retryCount < maxRetries) {
        setTimeout(() => {
          setRetryCount((c) => c + 1);
        }, 1000 * Math.pow(2, retryCount));
      }
    };

    return () => es.close();
  }, [url, retryCount]);
}
```

## Testing Strategy

### Dual Testing Approach

本系统采用单元测试和属性测试相结合的测试策略：

1. **单元测试**: 验证具体示例和边界情况
2. **属性测试**: 验证应在所有输入上成立的通用属性

### Property-Based Testing Framework

使用 **Hypothesis** (Python) 和 **fast-check** (TypeScript) 进行属性测试。

#### Python (Backend)

```python
from hypothesis import given, strategies as st, settings

@settings(max_examples=100)
@given(st.text(min_size=1, max_size=50))
def test_kb_capability_roundtrip(kb_name):
    """Property 1: KB Capability Configuration Round-Trip"""
    # Test implementation
    pass
```

#### TypeScript (Frontend)

```typescript
import fc from "fast-check";

test("Property 6: Dynamic Form Component Mapping", () => {
  fc.assert(
    fc.property(
      fc.record({
        type: fc.constantFrom("string", "integer", "boolean", "array"),
        ui_component: fc.constantFrom(
          "select",
          "slider",
          "switch",
          "multi-select"
        ),
      }),
      (schema) => {
        // Test implementation
      }
    ),
    { numRuns: 100 }
  );
});
```

### Test Categories

1. **API Tests** (`tests/server/api/`)

   - KB Config API tests
   - Algorithms API tests
   - Domains API tests
   - LLM Gateway API tests

2. **Frontend Tests** (`frontend/tests/`)

   - Component unit tests
   - Store tests
   - Integration tests

3. **Property Tests** (`tests/properties/`)
   - Round-trip properties
   - Invariant properties
   - Metamorphic properties

### Test Annotations

每个属性测试必须使用以下格式注释：

```python
# **Feature: capability-visualization, Property 1: KB Capability Configuration Round-Trip**
# **Validates: Requirements 1.2, 12.1**
```

```typescript
// **Feature: capability-visualization, Property 6: Dynamic Form Component Mapping**
// **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
```
