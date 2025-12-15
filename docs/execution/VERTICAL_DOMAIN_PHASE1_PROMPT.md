# OmniRAG 垂直领域增强 - 第一阶段开发指南

> **版本**: v1.0 | **日期**: 2025-12-14
> **阶段目标**: 基础设施搭建 + 多云算力 Provider + 真实数据验证
> **预计周期**: 2 周
> **核心原则**: 真实数据驱动开发，拒绝空壳 Mock

---

## 🎯 第一阶段总览

### 阶段定位

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PHASE 1: INFRASTRUCTURE & COMPUTE LAYER                  │
│                        "地基要稳，数据要真"                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   本阶段交付物:                                                              │
│   ├── 1. 多云算力 Provider Registry (DashScope/火山/Azure/DeepSeek)         │
│   ├── 2. 成本估算器 + 预算控制                                               │
│   ├── 3. 增强现有 core/llm/gateway.py                                        │
│   ├── 4. 真实 API 调用验证 (非 Mock)                                         │
│   └── 5. 完整的数据库 Schema (支持后续阶段)                                   │
│                                                                              │
│   验收标准:                                                                  │
│   ├── ✅ 至少 2 个云 Provider 完成真实 API 调通                              │
│   ├── ✅ 真实调用 VLM 处理 10+ 张测试图片                                    │
│   ├── ✅ 成本追踪数据持久化到数据库                                          │
│   ├── ✅ 故障转移链在真实故障场景下生效                                      │
│   └── ✅ 现有 RAG 功能回归测试通过                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 为什么强调「真实数据」?

| 问题 | Mock 开发的风险 | 真实数据开发的价值 |
|:-----|:----------------|:-------------------|
| API 兼容性 | Mock 无法暴露各 Provider API 差异 | 立即发现参数格式、错误码差异 |
| 成本估算 | Mock 成本都是假数字 | 真实调用产生真实成本数据 |
| 延迟优化 | Mock 延迟不真实 | 建立真实的性能基线 |
| 数据库设计 | Mock 数据结构不完整 | 真实数据驱动完整 Schema |
| 错误处理 | Mock 无法模拟真实错误 | 真实错误驱动健壮代码 |

---

## 📋 Phase 1.1: 理解现有实现 (Day 1-2)

### 目标
在写任何新代码之前，深入理解 core 中已有的实现，避免重复造轮子。

### 任务清单

#### 1.1.1 分析 core/llm/ 模块

```yaml
分析任务:
  文件: "core/llm/gateway.py"
  理解要点:
    - 现有 Provider 加载机制是怎样的？
    - 熔断/降级逻辑如何实现？
    - 用量记录当前存储在哪里？
    - 与 core/llm/registry.py 的关系？
  
  输出物:
    - 绘制现有 Gateway 类图 (Mermaid)
    - 识别可复用的组件
    - 标注需要增强的方法

  文件: "core/llm/provider_config.py"
  理解要点:
    - DEFAULT_CONFIG 结构详解
    - REQUIRED_ENV 映射关系
    - provider_category 分类逻辑
    - 如何添加新 Provider？
  
  输出物:
    - Provider 配置示例模板
    - 新增 Provider 的检查清单
```

#### 1.1.2 分析 core/embedding/ 模块

```yaml
分析任务:
  文件: "core/embedding/provider_embedder.py"
  理解要点:
    - 现有 embedding 调用链路
    - 是否有缓存机制？
    - 与 EmbedderRegistry 的关系
  
  输出物:
    - Embedding 调用流程图
    - 缓存扩展点识别
```

#### 1.1.3 分析 core/capabilities/ 模块

```yaml
分析任务:
  文件: "core/capabilities/manifest.yaml"
  理解要点:
    - 能力定义 Schema
    - config_schema 格式规范
    - implementation 映射方式
    - requires 依赖声明
  
  输出物:
    - 能力卡片模板
    - 新能力接入规范
```

#### 1.1.4 分析 server/database.py

```yaml
分析任务:
  文件: "server/database.py"
  理解要点:
    - 现有表结构
    - ORM 模型定义
    - 迁移机制 (如有)
  
  输出物:
    - 现有 ERD 图
    - 新增表设计方案
```

### 交付物
- [ ] `docs/tech/phase1_existing_analysis.md` - 现有实现分析报告
- [ ] `docs/tech/phase1_enhancement_plan.md` - 增强计划 (具体到方法级别)

---

## 📋 Phase 1.2: 数据库 Schema 设计与实现 (Day 3-4)

### 目标
设计完整的数据库 Schema，支撑 Phase 1-5 所有阶段的数据需求。

### 为什么先做数据库？

```
真实数据开发原则:
1. 数据库 Schema 是数据的「真相来源」
2. 没有正确的 Schema，真实数据无处存放
3. Schema 设计不完整 → 后期重构成本极高
4. 先设计 Schema → 再开发逻辑 → 数据自然流入
```

### 任务清单

#### 1.2.1 设计算力 Provider 相关表

```sql
-- provider_registry: Provider 注册信息
-- 存储各云 Provider 的配置和状态

CREATE TABLE IF NOT EXISTS compute_providers (
    id TEXT PRIMARY KEY,                    -- provider_id: dashscope, volcengine, azure, deepseek
    name TEXT NOT NULL,
    name_en TEXT,
    category TEXT NOT NULL,                 -- domestic, foreign
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 10,            -- 路由优先级，数字越小优先级越高
    
    -- 端点配置 (JSON)
    endpoints JSONB NOT NULL,               -- {"chat": "...", "embedding": "...", "vision": "..."}
    
    -- 模型列表 (JSON)
    models JSONB NOT NULL,                  -- [{"id": "qwen-max", "cost_per_1k": 0.02, ...}]
    
    -- 限流配置
    rate_limits JSONB,                      -- {"rpm": 1000, "tpm": 1000000}
    
    -- 健康状态
    is_healthy BOOLEAN DEFAULT true,
    last_health_check TIMESTAMP,
    health_check_endpoint TEXT,
    
    -- 熔断状态
    circuit_breaker_failures INTEGER DEFAULT 0,
    circuit_breaker_open_until TIMESTAMP,
    
    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_providers_category ON compute_providers(category);
CREATE INDEX idx_providers_enabled ON compute_providers(enabled);
CREATE INDEX idx_providers_priority ON compute_providers(priority);
```

#### 1.2.2 设计成本追踪表

```sql
-- compute_cost_records: 算力成本记录
-- 每次 API 调用都记录成本，用于预算控制和分析

CREATE TABLE IF NOT EXISTS compute_cost_records (
    id SERIAL PRIMARY KEY,
    
    -- 请求标识
    request_id TEXT NOT NULL,               -- UUID
    channel_id TEXT,                        -- 关联的 Channel
    user_id TEXT,                           -- 关联的用户
    
    -- Provider 信息
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    
    -- 任务信息
    task_type TEXT NOT NULL,                -- chat, embedding, vision, batch
    
    -- Token/资源消耗
    input_tokens INTEGER,
    output_tokens INTEGER,
    image_count INTEGER,
    
    -- 成本 (USD)
    cost_usd DECIMAL(10, 6) NOT NULL,
    
    -- 性能指标
    latency_ms INTEGER,
    cached BOOLEAN DEFAULT false,
    
    -- 状态
    success BOOLEAN NOT NULL,
    error_message TEXT,
    
    -- 时间
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 用于快速查询
    date_partition DATE GENERATED ALWAYS AS (DATE(created_at)) STORED
);

-- 索引 (针对常见查询优化)
CREATE INDEX idx_cost_records_date ON compute_cost_records(date_partition);
CREATE INDEX idx_cost_records_channel ON compute_cost_records(channel_id, date_partition);
CREATE INDEX idx_cost_records_provider ON compute_cost_records(provider_id, date_partition);
CREATE INDEX idx_cost_records_task ON compute_cost_records(task_type, date_partition);
```

#### 1.2.3 设计预算配置表

```sql
-- budget_configs: 预算配置
-- 支持全局、Channel 级、用户级预算控制

CREATE TABLE IF NOT EXISTS budget_configs (
    id SERIAL PRIMARY KEY,
    
    -- 预算范围
    scope TEXT NOT NULL,                    -- global, channel, user
    scope_id TEXT,                          -- channel_id 或 user_id，global 时为 NULL
    
    -- 预算限额 (USD)
    daily_limit DECIMAL(10, 2),
    monthly_limit DECIMAL(10, 2),
    
    -- 告警阈值 (百分比)
    alert_threshold DECIMAL(3, 2) DEFAULT 0.80,
    hard_stop_threshold DECIMAL(3, 2) DEFAULT 0.95,
    
    -- 状态
    is_active BOOLEAN DEFAULT true,
    
    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(scope, scope_id)
);

-- 默认全局预算
INSERT INTO budget_configs (scope, scope_id, daily_limit, monthly_limit)
VALUES ('global', NULL, 100.00, 2000.00)
ON CONFLICT DO NOTHING;
```

#### 1.2.4 设计领域配置表 (为 Phase 2+ 预留)

```sql
-- domain_configs: 垂直领域配置
-- 为后续阶段预留，Phase 1 先创建表结构

CREATE TABLE IF NOT EXISTS domain_configs (
    id TEXT PRIMARY KEY,                    -- domain_id: metaphysics_chinese, comic_four_panel
    name TEXT NOT NULL,
    name_en TEXT,
    
    -- 本体定义 (JSON/YAML)
    ontology JSONB NOT NULL,
    
    -- 视觉 Schema
    visual_schema JSONB,
    
    -- 叙事 Schema
    narrative_schema JSONB,
    
    -- 解读规则
    interpretation_rules JSONB,
    
    -- GPU 需求
    gpu_requirements JSONB,                 -- {"min_vram_gb": 8, "recommended_vram_gb": 24}
    
    -- 状态
    enabled BOOLEAN DEFAULT true,
    
    -- 元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 1.2.5 创建视图用于成本分析

```sql
-- 每日成本汇总视图
CREATE OR REPLACE VIEW daily_cost_summary AS
SELECT 
    date_partition AS date,
    provider_id,
    task_type,
    COUNT(*) AS request_count,
    SUM(cost_usd) AS total_cost,
    AVG(latency_ms) AS avg_latency,
    SUM(CASE WHEN cached THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS cache_hit_rate,
    SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS success_rate
FROM compute_cost_records
GROUP BY date_partition, provider_id, task_type;

-- Channel 成本视图
CREATE OR REPLACE VIEW channel_cost_summary AS
SELECT 
    channel_id,
    date_partition AS date,
    SUM(cost_usd) AS total_cost,
    COUNT(*) AS request_count
FROM compute_cost_records
WHERE channel_id IS NOT NULL
GROUP BY channel_id, date_partition;
```

### 交付物
- [ ] `core/storage/migrations/001_compute_infrastructure.sql` - 完整迁移脚本
- [ ] `server/models.py` 更新 - 添加 ORM 模型
- [ ] 数据库迁移执行验证

---

## 📋 Phase 1.3: 增强现有 LLM Gateway (Day 5-7)

### 目标
在现有 `core/llm/gateway.py` 基础上增强，而非新建 Gateway。

### 核心原则

```
❌ 错误做法: 创建新的 core/compute/new_gateway.py
✅ 正确做法: 增强现有 core/llm/gateway.py，添加 Provider 选择能力
```

### 任务清单

#### 1.3.1 扩展 provider_config.py

```python
# 在现有 DEFAULT_CONFIG 基础上添加新 Provider
# 文件: core/llm/provider_config.py

# 新增 Provider 配置
ENHANCED_PROVIDER_CONFIGS = {
    # 保留现有配置...
    
    # 新增: 火山方舟
    "volcengine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "VOLCENGINE_API_KEY",
        "models": {
            "doubao-pro-256k": {
                "context_length": 262144,
                "cost_per_1k_input": 0.005,
                "cost_per_1k_output": 0.009,
            },
            "doubao-lite-128k": {
                "context_length": 131072,
                "cost_per_1k_input": 0.0008,
                "cost_per_1k_output": 0.001,
            },
        },
        "category": "domestic",
        "priority": 2,
    },
    
    # 新增: Azure OpenAI
    "azure": {
        "base_url_env": "AZURE_OPENAI_ENDPOINT",
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "api_version_env": "AZURE_OPENAI_API_VERSION",
        "models": {
            "gpt-4o": {
                "deployment_env": "AZURE_GPT4O_DEPLOYMENT",
                "context_length": 128000,
                "cost_per_1k_input": 0.005,
                "cost_per_1k_output": 0.015,
            },
            "gpt-4o-mini": {
                "deployment_env": "AZURE_GPT4O_MINI_DEPLOYMENT",
                "context_length": 128000,
                "cost_per_1k_input": 0.00015,
                "cost_per_1k_output": 0.0006,
            },
        },
        "category": "foreign",
        "priority": 3,
    },
    
    # 新增: DeepSeek (高性价比)
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": {
            "deepseek-chat": {
                "context_length": 65536,
                "cost_per_1k_input": 0.0001,
                "cost_per_1k_output": 0.0002,
            },
            "deepseek-reasoner": {
                "context_length": 65536,
                "cost_per_1k_input": 0.0004,
                "cost_per_1k_output": 0.0016,
            },
        },
        "category": "domestic",
        "priority": 4,
    },
}
```

#### 1.3.2 增强 gateway.py

```yaml
增强点:
  1. 添加 Provider 路由逻辑:
     - cost_first: 成本优先
     - performance_first: 性能优先
     - balanced: 平衡策略
  
  2. 增强故障转移:
     - 添加 failover_chain 配置
     - 自动切换到备选 Provider
  
  3. 成本追踪:
     - 每次调用记录成本
     - 写入 compute_cost_records 表
  
  4. 预算检查:
     - 调用前检查预算
     - 超预算自动降级或拒绝

保持兼容:
  - 现有调用方式不变
  - 新参数都有默认值
  - 所有测试必须通过
```

#### 1.3.3 真实 API 验证脚本

```python
# tests/integration/test_provider_real_api.py
"""
真实 API 调用验证 - 非 Mock 测试
运行前确保环境变量已配置
"""

import pytest
import os
from core.llm.gateway import LLMGateway

# 标记为集成测试，需要真实 API Key
pytestmark = pytest.mark.integration


class TestRealProviderAPI:
    """真实 Provider API 测试"""
    
    @pytest.fixture
    def dashscope_gateway(self):
        """DashScope Gateway"""
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            pytest.skip("DASHSCOPE_API_KEY not set")
        return LLMGateway(provider="dashscope")
    
    @pytest.fixture
    def volcengine_gateway(self):
        """火山方舟 Gateway"""
        api_key = os.environ.get("VOLCENGINE_API_KEY")
        if not api_key:
            pytest.skip("VOLCENGINE_API_KEY not set")
        return LLMGateway(provider="volcengine")
    
    @pytest.fixture
    def deepseek_gateway(self):
        """DeepSeek Gateway"""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        return LLMGateway(provider="deepseek")
    
    # ─────────────────────────────────────────────────────────────
    # Chat API 测试
    # ─────────────────────────────────────────────────────────────
    
    async def test_dashscope_chat_real(self, dashscope_gateway):
        """DashScope 真实 Chat API 调用"""
        response = await dashscope_gateway.chat(
            messages=[{"role": "user", "content": "Say 'Hello OmniRAG' in exactly 3 words"}],
            model="qwen-turbo",
            max_tokens=50
        )
        
        assert response is not None
        assert "content" in response
        # 验证成本记录已写入数据库
        # ...
    
    async def test_volcengine_chat_real(self, volcengine_gateway):
        """火山方舟真实 Chat API 调用"""
        response = await volcengine_gateway.chat(
            messages=[{"role": "user", "content": "Say 'Hello OmniRAG' in exactly 3 words"}],
            model="doubao-lite-128k",
            max_tokens=50
        )
        
        assert response is not None
    
    async def test_deepseek_chat_real(self, deepseek_gateway):
        """DeepSeek 真实 Chat API 调用"""
        response = await deepseek_gateway.chat(
            messages=[{"role": "user", "content": "Say 'Hello OmniRAG' in exactly 3 words"}],
            model="deepseek-chat",
            max_tokens=50
        )
        
        assert response is not None
    
    # ─────────────────────────────────────────────────────────────
    # Embedding API 测试
    # ─────────────────────────────────────────────────────────────
    
    async def test_dashscope_embedding_real(self, dashscope_gateway):
        """DashScope 真实 Embedding API 调用"""
        texts = ["OmniRAG 垂直领域增强", "多云算力 Provider"]
        
        embeddings = await dashscope_gateway.embed(
            texts=texts,
            model="text-embedding-v3"
        )
        
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1024  # text-embedding-v3 维度
    
    # ─────────────────────────────────────────────────────────────
    # Vision API 测试 (使用真实图片)
    # ─────────────────────────────────────────────────────────────
    
    async def test_dashscope_vision_real(self, dashscope_gateway):
        """DashScope 真实 VLM API 调用"""
        # 使用项目中的测试图片
        test_image_path = "data/samples/test_image.jpg"
        if not os.path.exists(test_image_path):
            pytest.skip("Test image not found")
        
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        
        response = await dashscope_gateway.vision(
            images=[image_bytes],
            prompt="描述这张图片的主要内容",
            model="qwen-vl-plus"
        )
        
        assert response is not None
        assert len(response) > 10  # 应该有实际描述
    
    # ─────────────────────────────────────────────────────────────
    # 故障转移测试
    # ─────────────────────────────────────────────────────────────
    
    async def test_failover_real(self):
        """真实故障转移测试"""
        # 配置一个无效的 primary，验证是否自动切换
        gateway = LLMGateway(
            provider="invalid_provider",
            fallback_providers=["dashscope", "deepseek"]
        )
        
        # 应该自动切换到 fallback
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=10
        )
        
        assert response is not None
        assert gateway.last_used_provider in ["dashscope", "deepseek"]
    
    # ─────────────────────────────────────────────────────────────
    # 成本追踪验证
    # ─────────────────────────────────────────────────────────────
    
    async def test_cost_tracking_real(self, dashscope_gateway):
        """验证成本追踪写入数据库"""
        from server.database import get_db
        
        # 执行调用
        await dashscope_gateway.chat(
            messages=[{"role": "user", "content": "Test"}],
            model="qwen-turbo",
            max_tokens=10
        )
        
        # 验证数据库记录
        db = get_db()
        records = db.query(
            "SELECT * FROM compute_cost_records ORDER BY created_at DESC LIMIT 1"
        )
        
        assert len(records) > 0
        assert records[0]["provider_id"] == "dashscope"
        assert records[0]["cost_usd"] > 0
```

### 交付物
- [ ] `core/llm/provider_config.py` 增强
- [ ] `core/llm/gateway.py` 增强
- [ ] `tests/integration/test_provider_real_api.py` - 真实 API 测试
- [ ] 至少 2 个 Provider 真实调通的验证报告

---

## 📋 Phase 1.4: 创建 core/compute/ 模块 (Day 8-10)

### 目标
创建算力基础设施模块，作为统一的多云 Provider 管理层。

### 模块结构

```
core/compute/
├── __init__.py                 # 模块入口，导出公共接口
├── provider_registry.py        # Provider 注册器 (核心)
├── cost_estimator.py           # 成本估算器
├── cost_tracker.py             # 成本追踪器 (写数据库)
├── providers.yaml              # Provider 配置
└── providers/
    ├── __init__.py
    ├── base.py                 # Provider 基类
    ├── dashscope.py            # 阿里云百炼
    ├── volcengine.py           # 火山方舟
    ├── azure.py                # Azure OpenAI
    └── deepseek.py             # DeepSeek
```

### 任务清单

#### 1.4.1 创建 providers.yaml

```yaml
# core/compute/providers.yaml
# 真实配置，非示例

version: "1.0"

global_strategy:
  routing_strategy: "cost_first"
  failover_enabled: true
  max_retries: 3
  
  cache:
    enabled: true
    ttl_seconds: 3600

providers:
  dashscope:
    id: "dashscope"
    name: "阿里云百炼"
    category: "domestic"
    enabled: true
    priority: 1
    
    auth:
      env_vars:
        - "DASHSCOPE_API_KEY"
    
    endpoints:
      chat: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
      embedding: "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
      vision: "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    models:
      llm:
        - id: "qwen-max"
          cost_per_1k_tokens: 0.02
        - id: "qwen-plus"
          cost_per_1k_tokens: 0.004
        - id: "qwen-turbo"
          cost_per_1k_tokens: 0.002
      vlm:
        - id: "qwen-vl-max"
          cost_per_image: 0.01
        - id: "qwen-vl-plus"
          cost_per_image: 0.004
      embedding:
        - id: "text-embedding-v3"
          cost_per_1k_tokens: 0.0007
          dimension: 1024

  volcengine:
    id: "volcengine"
    name: "火山方舟"
    category: "domestic"
    enabled: true
    priority: 2
    # ... 完整配置

  deepseek:
    id: "deepseek"
    name: "DeepSeek"
    category: "domestic"
    enabled: true
    priority: 4
    # ... 完整配置

routing_rules:
  task_routing:
    - task_type: "simple_chat"
      preferred_providers: ["deepseek", "dashscope"]
      max_cost_per_request: 0.01
    
    - task_type: "vision_understanding"
      preferred_providers: ["dashscope", "volcengine"]
      max_cost_per_request: 0.05

  failover_chains:
    - primary: "dashscope"
      fallbacks: ["volcengine", "deepseek"]
```

#### 1.4.2 实现 cost_tracker.py

```python
# core/compute/cost_tracker.py
"""
成本追踪器 - 将每次调用的成本写入数据库
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from server.database import get_db_session


@dataclass
class CostRecord:
    """成本记录"""
    request_id: str
    provider_id: str
    model_id: str
    task_type: str
    input_tokens: int
    output_tokens: int
    image_count: int
    cost_usd: float
    latency_ms: int
    success: bool
    cached: bool = False
    error_message: Optional[str] = None
    channel_id: Optional[str] = None
    user_id: Optional[str] = None


class CostTracker:
    """成本追踪器"""
    
    def __init__(self):
        self._db = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_db_session()
        return self._db
    
    def track(self, record: CostRecord) -> None:
        """记录成本到数据库"""
        self.db.execute(
            """
            INSERT INTO compute_cost_records (
                request_id, channel_id, user_id,
                provider_id, model_id, task_type,
                input_tokens, output_tokens, image_count,
                cost_usd, latency_ms, cached, success, error_message
            ) VALUES (
                :request_id, :channel_id, :user_id,
                :provider_id, :model_id, :task_type,
                :input_tokens, :output_tokens, :image_count,
                :cost_usd, :latency_ms, :cached, :success, :error_message
            )
            """,
            {
                "request_id": record.request_id,
                "channel_id": record.channel_id,
                "user_id": record.user_id,
                "provider_id": record.provider_id,
                "model_id": record.model_id,
                "task_type": record.task_type,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "image_count": record.image_count,
                "cost_usd": record.cost_usd,
                "latency_ms": record.latency_ms,
                "cached": record.cached,
                "success": record.success,
                "error_message": record.error_message,
            }
        )
        self.db.commit()
    
    def get_daily_cost(self, date: datetime = None, channel_id: str = None) -> float:
        """获取每日成本"""
        date = date or datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        
        query = """
            SELECT COALESCE(SUM(cost_usd), 0) as total
            FROM compute_cost_records
            WHERE date_partition = :date
        """
        params = {"date": date_str}
        
        if channel_id:
            query += " AND channel_id = :channel_id"
            params["channel_id"] = channel_id
        
        result = self.db.execute(query, params).fetchone()
        return float(result["total"])
    
    def check_budget(self, channel_id: str = None) -> tuple[bool, float]:
        """检查预算是否超限"""
        # 获取预算配置
        scope = "channel" if channel_id else "global"
        scope_id = channel_id
        
        config = self.db.execute(
            """
            SELECT daily_limit, alert_threshold, hard_stop_threshold
            FROM budget_configs
            WHERE scope = :scope AND (scope_id = :scope_id OR scope_id IS NULL)
            AND is_active = true
            ORDER BY scope_id NULLS LAST
            LIMIT 1
            """,
            {"scope": scope, "scope_id": scope_id}
        ).fetchone()
        
        if not config:
            return True, 100.0  # 无预算配置，允许
        
        daily_cost = self.get_daily_cost(channel_id=channel_id)
        daily_limit = float(config["daily_limit"])
        remaining = daily_limit - daily_cost
        
        hard_stop = float(config["hard_stop_threshold"])
        if daily_cost >= daily_limit * hard_stop:
            return False, remaining
        
        return True, remaining


# 全局实例
_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
```

#### 1.4.3 真实数据验证测试

```python
# tests/integration/test_cost_tracking_real.py
"""
成本追踪真实数据验证
"""

import pytest
from datetime import datetime

from core.compute.cost_tracker import CostTracker, CostRecord, get_cost_tracker


@pytest.mark.integration
class TestCostTrackingReal:
    """成本追踪真实测试"""
    
    @pytest.fixture
    def tracker(self):
        return get_cost_tracker()
    
    async def test_track_and_query_real(self, tracker):
        """记录并查询成本"""
        # 记录
        record = CostRecord(
            request_id="test-001",
            provider_id="dashscope",
            model_id="qwen-turbo",
            task_type="chat",
            input_tokens=100,
            output_tokens=50,
            image_count=0,
            cost_usd=0.0003,
            latency_ms=200,
            success=True
        )
        tracker.track(record)
        
        # 查询验证
        daily_cost = tracker.get_daily_cost()
        assert daily_cost >= 0.0003
    
    async def test_budget_check_real(self, tracker):
        """预算检查真实测试"""
        allowed, remaining = tracker.check_budget()
        
        # 验证返回合理值
        assert isinstance(allowed, bool)
        assert isinstance(remaining, float)
        assert remaining >= 0 or not allowed
    
    async def test_daily_summary_view(self, tracker):
        """验证日汇总视图"""
        result = tracker.db.execute(
            "SELECT * FROM daily_cost_summary WHERE date = :date",
            {"date": datetime.now().strftime("%Y-%m-%d")}
        ).fetchall()
        
        # 应该有数据 (如果今天有调用)
        # 验证视图结构
        if result:
            assert "provider_id" in result[0]
            assert "total_cost" in result[0]
```

### 交付物
- [ ] `core/compute/__init__.py`
- [ ] `core/compute/provider_registry.py`
- [ ] `core/compute/cost_estimator.py`
- [ ] `core/compute/cost_tracker.py`
- [ ] `core/compute/providers.yaml`
- [ ] `core/compute/providers/*.py` (4 个 Provider)
- [ ] `tests/integration/test_cost_tracking_real.py`

---

## 📋 Phase 1.5: 集成与验证 (Day 11-14)

### 目标
完成 Phase 1 所有组件的集成，并通过真实数据验证。

### 任务清单

#### 1.5.1 集成 Gateway 与 Compute 模块

```yaml
集成点:
  1. core/llm/gateway.py 使用 core/compute/provider_registry.py:
     - Provider 选择委托给 Registry
     - 成本追踪通过 CostTracker
     - 预算检查在调用前执行
  
  2. 保持向后兼容:
     - 现有 gateway 调用方式不变
     - 新功能通过可选参数启用
```

#### 1.5.2 真实数据端到端测试

```python
# tests/e2e/test_phase1_e2e.py
"""
Phase 1 端到端测试 - 使用真实数据
"""

import pytest
import os

from core.llm.gateway import LLMGateway
from core.compute import get_compute_registry
from core.compute.cost_tracker import get_cost_tracker


@pytest.mark.e2e
class TestPhase1E2E:
    """Phase 1 端到端测试"""
    
    # ─────────────────────────────────────────────────────────────
    # 测试场景 1: 基础 Chat 调用 + 成本追踪
    # ─────────────────────────────────────────────────────────────
    
    async def test_chat_with_cost_tracking(self):
        """Chat 调用自动追踪成本"""
        gateway = LLMGateway(provider="dashscope")
        tracker = get_cost_tracker()
        
        # 记录调用前的成本
        cost_before = tracker.get_daily_cost()
        
        # 执行调用
        response = await gateway.chat(
            messages=[{"role": "user", "content": "Hello"}],
            model="qwen-turbo",
            max_tokens=20
        )
        
        # 验证成本增加
        cost_after = tracker.get_daily_cost()
        assert cost_after > cost_before
        
        # 验证响应
        assert response is not None
    
    # ─────────────────────────────────────────────────────────────
    # 测试场景 2: Provider 自动路由 (成本优先)
    # ─────────────────────────────────────────────────────────────
    
    async def test_cost_first_routing(self):
        """成本优先路由 - 自动选择最便宜的 Provider"""
        registry = get_compute_registry()
        
        # 设置成本优先策略
        response = await registry.execute({
            "task_type": "chat",
            "content": [{"role": "user", "content": "Test"}],
            "routing_strategy": "cost_first"
        })
        
        # 应该选择 DeepSeek (最便宜)
        assert response.provider_id == "deepseek"
    
    # ─────────────────────────────────────────────────────────────
    # 测试场景 3: VLM 真实图片处理
    # ─────────────────────────────────────────────────────────────
    
    async def test_vlm_real_images(self):
        """VLM 处理真实图片"""
        # 使用 data/samples/ 下的测试图片
        test_images_dir = "data/samples"
        images = []
        
        for filename in os.listdir(test_images_dir):
            if filename.endswith(('.jpg', '.png')):
                with open(os.path.join(test_images_dir, filename), 'rb') as f:
                    images.append(f.read())
        
        if not images:
            pytest.skip("No test images found")
        
        gateway = LLMGateway(provider="dashscope")
        
        # 处理每张图片
        results = []
        for img in images[:10]:  # 限制 10 张
            response = await gateway.vision(
                images=[img],
                prompt="简要描述这张图片的内容",
                model="qwen-vl-plus"
            )
            results.append(response)
        
        # 验证所有图片都有结果
        assert len(results) == min(10, len(images))
        for r in results:
            assert r is not None
            assert len(r) > 10
    
    # ─────────────────────────────────────────────────────────────
    # 测试场景 4: 故障转移
    # ─────────────────────────────────────────────────────────────
    
    async def test_failover_chain(self):
        """故障转移链测试"""
        registry = get_compute_registry()
        
        # 模拟 primary 故障
        registry.providers["dashscope"]._healthy = False
        
        try:
            response = await registry.execute({
                "task_type": "chat",
                "content": [{"role": "user", "content": "Test"}],
                "provider_id": "dashscope"  # 指定已故障的 Provider
            })
            
            # 应该自动切换到 fallback
            assert response.success
            assert response.provider_id in ["volcengine", "deepseek"]
        finally:
            # 恢复
            registry.providers["dashscope"]._healthy = True
    
    # ─────────────────────────────────────────────────────────────
    # 测试场景 5: 预算控制
    # ─────────────────────────────────────────────────────────────
    
    async def test_budget_control(self):
        """预算控制测试"""
        tracker = get_cost_tracker()
        
        # 设置一个很低的测试预算
        tracker.db.execute(
            """
            INSERT INTO budget_configs (scope, scope_id, daily_limit, hard_stop_threshold)
            VALUES ('channel', 'test-channel', 0.001, 0.95)
            ON CONFLICT (scope, scope_id) DO UPDATE SET daily_limit = 0.001
            """
        )
        tracker.db.commit()
        
        try:
            # 第一次调用应该成功
            gateway = LLMGateway(provider="dashscope", channel_id="test-channel")
            
            # 检查预算
            allowed, remaining = tracker.check_budget(channel_id="test-channel")
            
            if not allowed:
                # 预算已超，应该拒绝
                with pytest.raises(Exception, match="Budget exceeded"):
                    await gateway.chat(
                        messages=[{"role": "user", "content": "Test"}]
                    )
        finally:
            # 清理测试预算
            tracker.db.execute(
                "DELETE FROM budget_configs WHERE scope_id = 'test-channel'"
            )
            tracker.db.commit()
```

#### 1.5.3 准备测试数据

```yaml
测试数据准备:
  目录: "data/samples/"
  
  图片数据:
    - 至少 10 张不同类型的图片
    - 包含: 文档扫描件、图表、漫画、手写笔记
    - 格式: JPG, PNG
    - 用于: VLM 真实处理测试
  
  文本数据:
    - 至少 5 个不同领域的文本片段
    - 包含: 技术文档、命理文本、漫画台词
    - 用于: Embedding 真实生成测试
  
  创建脚本:
    文件: "scripts/prepare_test_data.py"
    功能:
      - 下载/生成测试数据
      - 验证数据完整性
      - 输出测试数据报告
```

#### 1.5.4 回归测试

```yaml
回归测试检查清单:
  - [ ] 现有 RAG Pipeline 正常工作
  - [ ] 现有 Chat API 正常响应
  - [ ] 现有 Embedding 生成正常
  - [ ] 现有文件上传/处理正常
  - [ ] 前端所有功能正常
  
  运行命令:
    - pytest tests/core/ -v
    - pytest tests/server/ -v
    - npm run test (前端)
```

### 交付物
- [ ] `tests/e2e/test_phase1_e2e.py` - 端到端测试
- [ ] `data/samples/` - 测试数据集
- [ ] `scripts/prepare_test_data.py` - 测试数据准备脚本
- [ ] Phase 1 验收报告 (markdown)

---

## 📊 Phase 1 验收标准

### 必须完成

| 编号 | 验收项 | 验证方式 | 状态 |
|:-----|:-------|:---------|:-----|
| 1.1 | 至少 2 个云 Provider 真实 API 调通 | 运行集成测试 | [ ] |
| 1.2 | VLM 真实处理 10+ 张图片 | E2E 测试日志 | [ ] |
| 1.3 | 成本追踪数据写入数据库 | 查询数据库验证 | [ ] |
| 1.4 | 故障转移在真实场景下生效 | 故障注入测试 | [ ] |
| 1.5 | 预算控制正常工作 | 预算超限测试 | [ ] |
| 1.6 | 回归测试 100% 通过 | CI 测试报告 | [ ] |

### 质量指标

| 指标 | 目标值 | 实际值 |
|:-----|:-------|:-------|
| 代码覆盖率 (新增代码) | > 80% | |
| 真实 API 调用成功率 | > 95% | |
| 平均延迟 (Chat) | < 2s | |
| 平均延迟 (VLM) | < 5s | |

### 文档交付

- [ ] `docs/tech/phase1_existing_analysis.md`
- [ ] `docs/tech/phase1_enhancement_plan.md`
- [ ] `docs/tech/phase1_completion_report.md`

---

## 🔜 下一阶段预告

**Phase 2: 领域抽象层 + 命理领域实现**

- 创建 `core/domains/` 模块
- 实现 `BaseDomainInterpreter` 基类
- 实现命理领域 (`metaphysics_chinese`)
- 真实命理图片解读测试

---

*Phase 1 开发指南 v1.0 | 2025-12-14 | OmniRAG Team*
