# OmniRAG 重构风险评估报告

> **评估日期**: 2025-12-08
> **评估范围**: `core/` (Legacy) 与 `server/` API 实现
> **参照文档**: `docs/tech/system-design.md`, `docs/architecture.md`, `docs/api-spec.md`, `docs/coding-standards.md`

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [Core 目录当前状态](#2-core-目录当前状态)
3. [Server 目录当前状态](#3-server-目录当前状态)
4. [方案对比分析](#4-方案对比分析)
5. [风险矩阵](#5-风险矩阵)
6. [推荐方案](#6-推荐方案)
7. [实施路线图](#7-实施路线图)

---

## 1. 执行摘要

### 1.1 核心发现

| 维度 | Core (Legacy) | Server (当前) | API-Spec (目标) | 差距 |
|:-----|:--------------|:--------------|:----------------|:-----|
| **多 Channel 支持** | ❌ 无 | ❌ 无 | ✅ 完整设计 | 🔴 高 |
| **用户认证** | ❌ 无 | 🟡 基础 JWT | ✅ JWT + API Key + RBAC | 🟡 中 |
| **文件管理 (OSS)** | ❌ 无 | ❌ 无 | ✅ 完整 API 设计 | 🔴 高 |
| **API 版本** | N/A | ❌ 无版本 | ✅ /api/v1 | 🟡 中 |
| **LangGraph 架构** | 🟡 部分实现 | 调用 core | ✅ 完整设计 | 🟡 中 |
| **DB Schema** | N/A | 🟡 6 表 | ✅ 16+ 表 | 🔴 高 |

### 1.2 决策建议

**推荐方案**: **渐进式重写 (Strangler Fig Pattern)**

- **保留**: `core/storage`, `core/embedding`, `core/reranker`, `core/vision` (已优化)
- **重写**: `core/ingestion`, `core/retrieval` LangGraph 管道
- **新增**: `server/` 全部 API 实现

---

## 2. Core 目录当前状态

### 2.1 模块健康度评估

```
core/
├── graph.py             [🟢 LOCKED] V4 Bridges，可复用
├── state.py             [🟢 LOCKED] 状态定义，需扩展 channel_id
│
├── storage/             [🟢 LOCKED]
│   ├── vector_store.py  ✅ Singleton Qdrant/Milvus
│   ├── keyword_store.py ✅ Singleton ES
│   ├── blob_store.py    ⚠️ 需增加 OSS 支持
│   ├── kb_config.py     ⚠️ 需增加 Channel 绑定
│   └── index_router.py  ✅ 双写可用
│
├── embedding/           [🟢 OK]
│   └── registry.py      ✅ Multi-provider，可复用
│
├── reranker/            [🟢 LOCKED]
│   └── cross_encoder.py ✅ Singleton 已优化
│
├── vision/              [🟢 LOCKED]
│   ├── layoutlm_parser  ✅ LRU 缓存已优化
│   └── yolo_detector    ✅ LRU 缓存已优化
│
├── llm/                 [🟡 OK]
│   └── gateway.py       ⚠️ 熔断需 Redis 持久化
│
├── ingestion/           [🟡 OK → 需重构]
│   ├── graph.py         ⚠️ 缺少 Channel 隔离
│   └── nodes/           ⚠️ 缺少批量/异步优化
│
├── retrieval/           [🟡 OK → 需重构]
│   ├── graph.py         ⚠️ 缺少 Multi-KB 支持
│   └── nodes/           ⚠️ 缺少语义缓存/幻觉检测
│
├── nodes/               [🔴 LEGACY]
│   └── *                ❌ 计划删除
│
├── algorithms/          [🟡 OK]
│   ├── raptor.py        ⚠️ 已标记废弃
│   └── graphrag.py      ⚠️ 已标记废弃
│
├── model_gateway/       [🟡 OK]
│   └── config_store.py  ⚠️ 缺少 Channel 绑定
│
└── pipeline/            [🟡 OK]
    └── registry.py      ✅ 可复用
```

### 2.2 代码行统计

| 模块 | 文件数 | 代码行 | 可复用率 |
|:-----|:------:|:------:|:--------:|
| storage/ | 9 | ~1200 | 85% |
| embedding/ | 4 | ~400 | 95% |
| reranker/ | 5 | ~350 | 100% |
| vision/ | 5 | ~300 | 100% |
| llm/ | 3 | ~500 | 80% |
| ingestion/ | 13 | ~800 | 40% |
| retrieval/ | 6 | ~600 | 50% |
| nodes/ (legacy) | 9 | ~700 | 0% |
| algorithms/ | 9 | ~1000 | 60% |
| **总计** | ~63 | ~5850 | **~55%** |

### 2.3 与设计文档差距

| 设计要求 | Core 现状 | 差距级别 |
|:---------|:----------|:---------|
| `channel_id` 数据隔离 | 未实现 | 🔴 高 |
| `session_id` 多 KB 绑定 | 未实现 | 🔴 高 |
| 四层配置覆盖 | 仅两层 | 🟡 中 |
| 语义缓存节点 | 未实现 | 🟡 中 |
| 幻觉检测节点 | 未实现 | 🟡 中 |
| OSS 文件管理 | 仅本地/MinIO | 🔴 高 |
| 批量摄取优化 | 未实现 | 🟡 中 |

---

## 3. Server 目录当前状态

### 3.1 API 实现评估

```
server/
├── main.py              [🟢 OK] FastAPI 入口，结构良好
├── routes.py            [🔴 需重构] 1453 行巨型文件
├── auth.py              [🟡 需扩展] 基础 JWT
├── models.py            [🔴 需重构] 缺少 10+ 表
├── schemas.py           [🟡 需扩展] 缺少 Channel/File 相关
├── database.py          [🟢 OK] SQLAlchemy 配置
├── config.py            [🟡 需扩展] 缺少 OSS 配置
├── health.py            [🟢 OK] 健康检查
└── api/
    └── ingest.py        [🟡 需重构] 缺少 Channel 隔离
```

### 3.2 routes.py 详细分析

| 函数 | 行数 | 状态 | 与 API-Spec 对齐 |
|:-----|:----:|:-----|:-----------------|
| `chat_stream` | ~290 | 🔴 过于复杂 | 缺少 session 管理 |
| `upload_document` | ~50 | 🟡 | 缺少 Channel 隔离 |
| `_validate_upload` | ~120 | 🟢 | 可复用 |
| `get_providers` | ~10 | 🟢 | 可复用 |
| `set_providers` | ~20 | 🟡 | 缺少 Channel 绑定 |
| `chat_sessions_*` | ~30 | 🟡 | 需要重构为 DB 持久化 |
| `metrics_*` | ~40 | 🟢 | 可复用 |

### 3.3 与 API-Spec 差距

| API-Spec 要求 | Server 现状 | 需新增 |
|:--------------|:------------|:-------|
| `/api/v1/auth/register` | ❌ 无 | ✅ |
| `/api/v1/auth/login` | 🟡 部分 | 完善 |
| `/api/v1/auth/api-keys` | ❌ 无 | ✅ |
| `/api/v1/channels/*` | ❌ 无 | ✅ |
| `/api/v1/kb/*` | 🟡 部分 | 完善 |
| `/api/v1/files/*` | ❌ 无 | ✅ |
| `/api/v1/ingest/*` | 🟡 部分 | 完善 |
| `/api/v1/chat/sessions/*` | 🟡 内存 | 改为 DB |
| `/api/v1/retrieval/*` | ❌ 无 | ✅ |
| `/api/v1/config/*` | 🟡 部分 | 完善 |

### 3.4 DB Schema 差距

| API-Spec 要求 | Server models.py | 状态 |
|:--------------|:-----------------|:-----|
| `users` | ❌ 无 | 🔴 需新增 |
| `channels` | ❌ 无 | 🔴 需新增 |
| `channel_members` | ❌ 无 | 🔴 需新增 |
| `knowledge_bases` | 部分 (`kb_configs`) | 🟡 需重构 |
| `documents` | 部分 (`kb_documents`) | 🟡 需重构 |
| `files` | ❌ 无 | 🔴 需新增 |
| `folders` | ❌ 无 | 🔴 需新增 |
| `file_kb_links` | ❌ 无 | 🔴 需新增 |
| `chat_sessions` | ❌ 无 (内存) | 🔴 需新增 |
| `chat_messages` | ❌ 无 | 🔴 需新增 |
| `api_keys` | ❌ 无 | 🔴 需新增 |
| `upload_sessions` | ❌ 无 | 🔴 需新增 |
| `providers` | ✅ 有 | 🟡 需扩展 |
| `model_configs` | ✅ 有 | 🟢 OK |

---

## 4. 方案对比分析

### 4.1 方案 A: 完全移除 Core，全新重写

```
优点:
+ 无历史包袱，架构纯净
+ 可直接按设计文档实现
+ 不存在兼容性问题

缺点:
- 工作量极大 (预估 4-6 周)
- 已优化的 Singleton/LRU 需重写
- 风险最高

风险等级: 🔴 高
```

### 4.2 方案 B: 在 Core 基础上渐进重构

```
优点:
+ 工作量适中 (预估 2-3 周)
+ 可复用 55% 已验证代码
+ 风险可控，可分阶段交付

缺点:
- 需处理历史兼容性
- 部分代码需要较大改动

风险等级: 🟡 中
```

### 4.3 方案 C: 保持 Core 不变，仅扩展 Server

```
优点:
+ 工作量最小 (预估 1-2 周)
+ Core 稳定，不引入新风险

缺点:
- 无法实现设计文档要求
- Channel 隔离无法在 Core 层实现
- 技术债务积累

风险等级: 🟡 中 (短期) / 🔴 高 (长期)
```

### 4.4 决策矩阵

| 维度 | 方案 A (全新) | 方案 B (渐进) | 方案 C (仅扩展) |
|:-----|:------------:|:------------:|:--------------:|
| 开发周期 | 6 周 | 3 周 | 2 周 |
| 风险等级 | 🔴 高 | 🟡 中 | 🟡→🔴 |
| 代码复用 | 0% | 55% | 100% |
| 架构对齐 | 100% | 90% | 50% |
| 可维护性 | 🟢 | 🟢 | 🔴 |
| **推荐度** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

---

## 5. 风险矩阵

### 5.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|:-----|:----:|:----:|:---------|
| LangGraph 管道重构导致回归 | 中 | 高 | 保留 V4 Bridge，渐进迁移 |
| 多 Channel 数据隔离漏洞 | 中 | 严重 | RLS Policy + 单元测试 |
| OSS 大文件上传失败 | 中 | 中 | 分片上传 + 重试机制 |
| 性能退化 (Singleton 丢失) | 低 | 高 | 保留已优化模块 |
| DB 迁移数据丢失 | 低 | 严重 | 渐进式 Schema 迁移 |

### 5.2 业务风险

| 风险 | 概率 | 影响 | 缓解措施 |
|:-----|:----:|:----:|:---------|
| 重构期间系统不可用 | 低 | 高 | 并行开发，不影响现有 |
| API 不兼容导致前端故障 | 中 | 中 | API 版本控制 /api/v1 |
| 100TB 数据迁移延迟 | 高 | 中 | 后台异步迁移脚本 |

---

## 6. 推荐方案

### 6.1 总体策略: 渐进式重写 (Strangler Fig Pattern)

```
                          ┌─────────────────────────────────────┐
                          │          新架构 (Target)            │
                          │  ┌───────────────────────────────┐  │
                          │  │   Server V2 (/api/v1/*)       │  │
                          │  │   - 多 Channel                │  │
                          │  │   - 用户认证 + RBAC           │  │
                          │  │   - 文件管理 (OSS)            │  │
                          │  └───────────────────────────────┘  │
                          │                 ↓                    │
Phase 1 ─────────────────▶│  ┌───────────────────────────────┐  │
                          │  │   Core V2                     │  │
                          │  │   - state.py + channel_id     │  │
                          │  │   - 复用 storage/embedding/   │  │
                          │  │   - 复用 reranker/vision      │  │
                          │  │   - 重构 ingestion/retrieval  │  │
                          │  └───────────────────────────────┘  │
                          └─────────────────────────────────────┘
                                             ↑
Phase 0 (现状) ──────────▶ ┌─────────────────┴─────────────────┐
                          │          Legacy (Deprecated)       │
                          │  - core/nodes/  → 删除             │
                          │  - 旧 API 路由  → /api/deprecated  │
                          └─────────────────────────────────────┘
```

### 6.2 模块处理决策

| 模块 | 决策 | 理由 |
|:-----|:-----|:-----|
| `core/storage/` | **保留扩展** | Singleton 优化已完成，仅需增加 channel_id |
| `core/embedding/` | **保留** | 稳定，无需改动 |
| `core/reranker/` | **保留** | Singleton 已优化 |
| `core/vision/` | **保留** | LRU 缓存已优化 |
| `core/llm/` | **保留扩展** | 增加 Redis 熔断 |
| `core/state.py` | **扩展** | 增加 channel_id, session_id |
| `core/graph.py` | **保留** | V4 Bridge 工作正常 |
| `core/ingestion/` | **重构** | 增加 Channel 隔离，批量优化 |
| `core/retrieval/` | **重构** | 增加 Multi-KB，语义缓存 |
| `core/nodes/` | **删除** | Legacy，已被 V4 替代 |
| `core/algorithms/` | **保留** | 按需使用 |
| `server/routes.py` | **拆分重写** | 单文件过大，需模块化 |
| `server/models.py` | **重写** | 与 API-Spec 对齐 |
| `server/auth.py` | **扩展** | 增加 RBAC + API Key |

---

## 7. 实施路线图

### Phase 0: 准备 (Day 1-2)

```
□ 创建 feature 分支
□ 设置 DB 迁移工具 (Alembic)
□ 编写新 Schema 迁移脚本
□ 创建 server/api/v1/ 目录结构
```

### Phase 1: 核心扩展 (Day 3-7)

```
□ 扩展 core/state.py (channel_id, session_id)
□ 扩展 core/storage/ (Channel 隔离 prefix)
□ 扩展 core/llm/gateway.py (Redis 熔断)
□ 新增 server/models_v2.py (完整 Schema)
□ 执行 DB 迁移
```

### Phase 2: 认证与授权 (Day 8-10)

```
□ 实现 server/api/v1/auth.py
  - POST /register
  - POST /login
  - POST /refresh
  - API Key CRUD
□ 实现 RBAC 中间件
□ 实现 RLS Policy
```

### Phase 3: Channel + KB API (Day 11-14)

```
□ 实现 server/api/v1/channels.py
□ 实现 server/api/v1/kb.py
□ 重构 core/ingestion/ (Channel 隔离)
□ 单元测试 > 80%
```

### Phase 4: 文件管理 (Day 15-18)

```
□ 实现 core/storage/oss_store.py
□ 实现 server/api/v1/files.py
  - 文件夹管理
  - 上传 (直接 + 预签名)
  - 下载
  - RAG 融合
□ OSS 分片上传测试
```

### Phase 5: 聊天 + 检索 (Day 19-21)

```
□ 重构 core/retrieval/ (Multi-KB)
□ 实现 server/api/v1/chat.py
□ 实现 server/api/v1/retrieval.py
□ 实现语义缓存节点
```

### Phase 6: 清理 + 上线 (Day 22-25)

```
□ 删除 core/nodes/
□ 废弃旧 API 路由
□ 性能测试
□ 安全审计
□ 生产部署
```

---

## 附录: 工作量估算

| 阶段 | 工作项 | 人天 |
|:-----|:-------|:----:|
| Phase 0 | 准备 | 2 |
| Phase 1 | 核心扩展 | 5 |
| Phase 2 | 认证授权 | 3 |
| Phase 3 | Channel + KB | 4 |
| Phase 4 | 文件管理 | 4 |
| Phase 5 | 聊天检索 | 3 |
| Phase 6 | 清理上线 | 4 |
| **总计** | | **25 人天** |

---

*本评估基于 2025-12-08 代码状态，如有重大变更请重新评估。*
