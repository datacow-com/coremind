# OmniRAG API 规范

> **版本**: v2.1 | **最后更新**: 2025-12-08
> **基准文档**: `docs/tech/system-design.md`, `docs/architecture.md`
> **数据规模**: 100TB ~ 500TB (多 Channel 隔离)

---

## 目录

1. [通用约定](#1-通用约定)
2. [API 版本管理](#2-api-版本管理)
3. [访问权限控制](#3-访问权限控制)
4. [认证 API](#4-认证-api)
5. [Channel API](#5-channel-api)
6. [知识库 API](#6-知识库-api)
7. [文件管理 API](#7-文件管理-api)
8. [文档摄取 API](#8-文档摄取-api)
9. [聊天 API](#9-聊天-api)
10. [检索 API](#10-检索-api)
11. [配置 API](#11-配置-api)
12. [系统 API](#12-系统-api)
13. [SSE 事件规范](#13-sse-事件规范)
14. [错误码定义](#14-错误码定义)
15. [Database Schema](#15-database-schema)

---

## 1. 通用约定

### 1.1 基础信息

| 项目 | 值 |
|:-----|:---|
| Base URL | `/api/v1` |
| 当前版本 | `v1` |
| 协议 | HTTPS (生产) / HTTP (开发) |
| 内容类型 | `application/json` (默认) |
| 流式响应 | `text/event-stream` (SSE) |
| 认证方式 | Bearer Token (JWT) / API Key |
| 字符编码 | UTF-8 |

### 1.2 请求头

```http
# 必填头
Authorization: Bearer <jwt_token>          # 或 X-API-Key: <api_key>
Content-Type: application/json
X-Channel-ID: <channel_id>                  # 必填 (除公共接口外)

# 可选头
X-Request-ID: <uuid>                        # 链路追踪
X-Idempotency-Key: <uuid>                   # 幂等性保证
Accept-Language: zh-CN                      # 国际化
X-Forwarded-For: <ip>                       # 原始 IP (代理场景)
```

### 1.3 响应格式

#### 成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "response_time_ms": 150
  }
}
```

#### 错误响应

```json
{
  "code": 40001,
  "message": "Knowledge base not found",
  "detail": {
    "kb_name": "unknown_kb",
    "available": ["legal", "product"]
  },
  "meta": {
    "request_id": "uuid",
    "api_version": "v1",
    "doc_url": "https://docs.example.com/errors/40001"
  }
}
```

### 1.4 分页参数

```
GET /api/v1/resource?page=1&page_size=20&sort_by=created_at&sort_order=desc
```

#### 分页响应

```json
{
  "code": 0,
  "data": {
    "items": [...],
    "pagination": {
      "total": 100,
      "page": 1,
      "page_size": 20,
      "total_pages": 5,
      "has_next": true,
      "has_prev": false
    }
  }
}
```

### 1.5 日期时间格式

所有日期时间使用 **ISO 8601** 格式，UTC 时区：

```
2025-12-08T12:00:00Z
2025-12-08T12:00:00.123Z
```

---

## 2. API 版本管理

### 2.1 版本策略

```
┌────────────────────────────────────────────────────────────┐
│                    API 版本演进策略                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│   URL 路径版本:  /api/v1/...  /api/v2/...                  │
│                                                             │
│   版本生命周期:                                             │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐               │
│   │  Alpha  │ →  │  Stable │ →  │Deprecated│ → 下线       │
│   │  (测试) │    │  (稳定) │    │ (废弃)   │               │
│   └─────────┘    └─────────┘    └─────────┘               │
│       1 月           12 月          6 月                   │
│                                                             │
│   兼容性承诺:                                               │
│   - 同一大版本内保证向后兼容                                │
│   - 废弃功能提前 6 个月通知                                 │
│   - 新增字段为可选，不影响现有客户端                        │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 2.2 当前版本

| 版本 | 状态 | 支持截止 | 说明 |
|:-----|:-----|:---------|:-----|
| `v1` | **Stable** | 2026-12-31 | 当前推荐版本 |

### 2.3 版本请求方式

```http
# 方式 1: URL 路径版本 (推荐)
GET /api/v1/kb

# 方式 2: Header 版本
GET /api/kb
X-API-Version: v1

# 方式 3: Query 参数
GET /api/kb?api_version=v1
```

优先级: URL 路径 > Header > Query > 默认 (latest)

### 2.4 版本响应头

```http
X-API-Version: v1
X-API-Deprecated: false
X-API-Sunset-Date: 2026-12-31  # 仅废弃版本返回
```

---

## 3. 访问权限控制

### 3.1 认证方式

```
┌─────────────────────────────────────────────────────────────┐
│                      认证方式矩阵                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  JWT Token   │    │   API Key    │    │   OAuth2.0   │  │
│  │  (用户会话)  │    │  (服务调用)  │    │  (第三方)    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  适用场景:                                                   │
│  - 前端应用        - 后端服务集成    - 第三方应用           │
│  - 移动端          - 自动化脚本      - SSO 登录             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 角色权限模型 (RBAC)

```
┌─────────────────────────────────────────────────────────────┐
│                     三级权限模型                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  系统级:    super_admin  →  管理所有 Channel                │
│                ↓                                             │
│  Channel级: channel_admin  →  管理 Channel 内所有资源       │
│                ↓                                             │
│  资源级:    member / viewer                                 │
│             - member: 读写 KB、上传文档、聊天                │
│             - viewer: 只读访问                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 权限矩阵

| 资源 | 操作 | super_admin | channel_admin | member | viewer |
|:-----|:-----|:-----------:|:-------------:|:------:|:------:|
| **Channel** | 创建 | ✅ | ❌ | ❌ | ❌ |
| | 读取 | ✅ | ✅ | ✅ | ✅ |
| | 更新 | ✅ | ✅ | ❌ | ❌ |
| | 删除 | ✅ | ❌ | ❌ | ❌ |
| | 成员管理 | ✅ | ✅ | ❌ | ❌ |
| **KB** | 创建 | ✅ | ✅ | ❌ | ❌ |
| | 读取 | ✅ | ✅ | ✅ | ✅ |
| | 更新 | ✅ | ✅ | ✅ | ❌ |
| | 删除 | ✅ | ✅ | ❌ | ❌ |
| **文件** | 上传 | ✅ | ✅ | ✅ | ❌ |
| | 下载 | ✅ | ✅ | ✅ | ✅ |
| | 删除 | ✅ | ✅ | ✅ | ❌ |
| **摄取** | 触发 | ✅ | ✅ | ✅ | ❌ |
| **聊天** | 发送 | ✅ | ✅ | ✅ | ✅ |
| **配置** | Provider | ✅ | ✅ | ❌ | ❌ |

### 3.4 API Key 管理

```http
# 创建 API Key
POST /api/v1/auth/api-keys
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "name": "backend-service",
  "scopes": ["kb:read", "kb:write", "chat:write"],
  "channel_ids": ["uuid1", "uuid2"],  // 可选，不填则继承用户权限
  "expires_at": "2026-12-31T23:59:59Z"
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "backend-service",
    "key": "omni_sk_xxxxxxxxxxxxxxxx",  // 仅创建时返回一次
    "prefix": "omni_sk_xxxx",
    "scopes": ["kb:read", "kb:write", "chat:write"],
    "created_at": "2025-12-08T12:00:00Z",
    "expires_at": "2026-12-31T23:59:59Z"
  }
}
```

### 3.5 Scope 定义

| Scope | 说明 |
|:------|:-----|
| `channel:read` | 读取 Channel 信息 |
| `channel:write` | 创建/更新 Channel |
| `kb:read` | 读取知识库、文档 |
| `kb:write` | 创建/更新知识库 |
| `file:read` | 下载文件 |
| `file:write` | 上传/删除文件 |
| `ingest:write` | 触发文档摄取 |
| `chat:read` | 读取聊天历史 |
| `chat:write` | 发送聊天消息 |
| `config:read` | 读取配置 |
| `config:write` | 修改配置 |
| `admin:*` | 管理员全权限 |

### 3.6 速率限制

```http
# 响应头
X-RateLimit-Limit: 1000           # 每分钟限制
X-RateLimit-Remaining: 950        # 剩余次数
X-RateLimit-Reset: 1702022400     # 重置时间戳
```

| 资源类型 | 免费用户 | 标准用户 | 企业用户 |
|:---------|:--------:|:--------:|:--------:|
| 聊天 API | 10/min | 100/min | 1000/min |
| 摄取 API | 5/min | 50/min | 500/min |
| 检索 API | 20/min | 200/min | 2000/min |
| 文件下载 | 10/min | 100/min | 无限制 |

---

## 4. 认证 API

### 2.1 用户注册

```http
POST /api/auth/register
```

#### 请求体

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "张三",
  "phone": "+8613800138000"  // 可选
}
```

#### 响应

```json
{
  "code": 0,
  "message": "Registration successful",
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "name": "张三",
    "created_at": "2025-12-08T12:00:00Z"
  }
}
```

#### 错误码

| Code | Message |
|:-----|:--------|
| 40001 | Email already registered |
| 40002 | Invalid email format |
| 40003 | Password too weak |

---

### 2.2 用户登录

```http
POST /api/auth/login
```

#### 请求体

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "name": "张三",
      "role": "user",
      "channels": [
        {
          "id": "uuid",
          "name": "legal",
          "display_name": "法律合规",
          "role": "admin"
        }
      ]
    }
  }
}
```

---

### 2.3 刷新令牌

```http
POST /api/auth/refresh
```

#### 请求体

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
  }
}
```

---

### 2.4 获取当前用户

```http
GET /api/auth/me
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "张三",
    "role": "user",
    "channels": [...],
    "created_at": "2025-12-08T12:00:00Z",
    "last_login_at": "2025-12-08T12:00:00Z"
  }
}
```

---

### 2.5 修改密码

```http
POST /api/auth/change-password
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

---

### 2.6 登出

```http
POST /api/auth/logout
Authorization: Bearer <token>
```

---

## 3. Channel API

### 3.1 获取用户 Channel 列表

```http
GET /api/channels
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "legal",
        "display_name": "法律合规",
        "description": "法律法规、判例、政策知识库",
        "role": "admin",
        "kb_count": 5,
        "doc_count": 12500,
        "created_at": "2025-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 3.2 创建 Channel (管理员)

```http
POST /api/channels
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "name": "legal",
  "display_name": "法律合规",
  "description": "法律法规、判例、政策知识库",
  "config": {
    "default_llm_provider": "dashscope",
    "default_embedding_model": "bge-m3",
    "max_kb_count": 50,
    "max_storage_gb": 1000
  }
}
```

---

### 3.3 获取 Channel 详情

```http
GET /api/channels/{channel_id}
Authorization: Bearer <token>
```

---

### 3.4 更新 Channel

```http
PATCH /api/channels/{channel_id}
Authorization: Bearer <token>
```

---

### 3.5 Channel 成员管理

```http
# 获取成员列表
GET /api/channels/{channel_id}/members

# 添加成员
POST /api/channels/{channel_id}/members
{
  "user_id": "uuid",
  "role": "member"  // admin | member | viewer
}

# 移除成员
DELETE /api/channels/{channel_id}/members/{user_id}

# 更新成员角色
PATCH /api/channels/{channel_id}/members/{user_id}
{
  "role": "admin"
}
```

---

## 4. 知识库 API

### 4.1 获取知识库列表

```http
GET /api/kb
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "regulations",
        "display_name": "法规库",
        "description": "法律法规文档",
        "doc_count": 2500,
        "chunk_count": 125000,
        "storage_size_mb": 8500,
        "config": {
          "chunking_mode": "semantic",
          "chunk_size": 800,
          "enable_graphrag": true
        },
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-12-08T12:00:00Z"
      }
    ]
  }
}
```

---

### 4.2 创建知识库

```http
POST /api/kb
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "name": "regulations",
  "display_name": "法规库",
  "description": "法律法规文档知识库",
  "config": {
    "chunking_mode": "semantic",
    "chunk_size": 800,
    "chunk_overlap": 80,
    "ocr_provider": "qwen-vl",
    "force_ocr": false,
    "embedding_model": "bge-m3",
    "vector_weight": 0.6,
    "keyword_weight": 0.4,
    "algorithms": {
      "enable_raptor": false,
      "enable_graphrag": true,
      "graph_community_level": 3
    }
  }
}
```

---

### 4.3 获取知识库详情

```http
GET /api/kb/{kb_name}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "regulations",
    "display_name": "法规库",
    "description": "...",
    "config": { ... },
    "effective_config": {
      // 合并后的生效配置 (Channel + KB + 默认值)
    },
    "stats": {
      "doc_count": 2500,
      "chunk_count": 125000,
      "storage_size_mb": 8500,
      "last_ingest_at": "2025-12-08T10:00:00Z"
    }
  }
}
```

---

### 4.4 更新知识库配置

```http
PATCH /api/kb/{kb_name}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "display_name": "法律法规库",
  "config": {
    "chunk_size": 1000,
    "enable_graphrag": true
  }
}
```

---

### 4.5 删除知识库

```http
DELETE /api/kb/{kb_name}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

### 4.6 获取知识库文档列表

```http
GET /api/kb/{kb_name}/documents?page=1&page_size=20
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "uuid",
        "filename": "contract_law.pdf",
        "file_type": "pdf",
        "file_size": 2048576,
        "page_count": 150,
        "chunk_count": 450,
        "status": "completed",
        "quality_score": 0.92,
        "created_at": "2025-12-08T10:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

---

### 4.7 删除文档

```http
DELETE /api/kb/{kb_name}/documents/{doc_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

## 7. 文件管理 API

> **设计背景**: 系统需要管理 100TB~500TB 海量文件，使用阿里云 OSS 作为文件存储后端。
> 文件管理与 RAG 系统融合，支持文件浏览、批量选择、直接 Ingest 到知识库。

### 7.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          文件管理系统架构                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────┐│
│  │   前端 UI    │ ←→  │  文件管理 API │ ←→  │     阿里云 OSS               ││
│  │  (文件浏览)  │     │              │     │  Channel/{folder}/{file}     ││
│  └──────────────┘     └──────┬───────┘     └──────────────────────────────┘│
│                              │                                              │
│                              ▼                                              │
│               ┌──────────────────────────────┐                             │
│               │       RAG 摄取管道           │                             │
│               │  (OSS 文件直接摄取)          │                             │
│               └──────────────────────────────┘                             │
│                                                                              │
│  数据隔离: 每个 Channel 独立 OSS Prefix (channel-{id}/)                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 文件夹管理

#### 获取文件夹列表

```http
GET /api/v1/files/folders?path=/&recursive=false
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| `path` | string | ❌ | 父路径，默认 `/` |
| `recursive` | boolean | ❌ | 是否递归，默认 `false` |

##### 响应

```json
{
  "code": 0,
  "data": {
    "current_path": "/legal/contracts",
    "folders": [
      {
        "name": "2024",
        "path": "/legal/contracts/2024",
        "file_count": 1250,
        "size_bytes": 5368709120,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2025-12-08T10:00:00Z"
      },
      {
        "name": "2025",
        "path": "/legal/contracts/2025",
        "file_count": 380,
        "size_bytes": 1610612736,
        "created_at": "2025-01-01T00:00:00Z"
      }
    ],
    "breadcrumb": [
      {"name": "根目录", "path": "/"},
      {"name": "legal", "path": "/legal"},
      {"name": "contracts", "path": "/legal/contracts"}
    ]
  }
}
```

#### 创建文件夹

```http
POST /api/v1/files/folders
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "path": "/legal/contracts/2025-Q4",
  "metadata": {
    "description": "2025年第四季度合同归档"
  }
}
```

#### 删除文件夹

```http
DELETE /api/v1/files/folders?path=/legal/contracts/temp&force=false
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

| 参数 | 说明 |
|:-----|:-----|
| `force` | 为 `true` 时删除非空文件夹，默认 `false` |

---

### 7.3 文件列表

#### 获取文件列表

```http
GET /api/v1/files?path=/legal/contracts&page=1&page_size=50
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| `path` | string | ❌ | 文件夹路径，默认 `/` |
| `file_type` | string | ❌ | 文件类型过滤 (pdf,docx,xlsx...) |
| `search` | string | ❌ | 文件名搜索 |
| `sort_by` | string | ❌ | 排序字段 (name/size/created_at) |
| `sort_order` | string | ❌ | asc/desc |
| `tag` | string | ❌ | 标签过滤 |

##### 响应

```json
{
  "code": 0,
  "data": {
    "path": "/legal/contracts",
    "files": [
      {
        "id": "uuid",
        "name": "供应商合同_2025.pdf",
        "path": "/legal/contracts/供应商合同_2025.pdf",
        "size_bytes": 2097152,
        "file_type": "pdf",
        "mime_type": "application/pdf",
        "oss_key": "channel-xxx/legal/contracts/uuid.pdf",
        "checksum_md5": "d41d8cd98f00b204e9800998ecf8427e",
        "tags": ["合同", "供应商"],
        "metadata": {
          "page_count": 25,
          "author": "法务部"
        },
        "rag_status": "indexed",  // pending, indexed, failed, none
        "kb_names": ["regulations"],  // 已关联的知识库
        "created_at": "2025-12-08T10:00:00Z",
        "updated_at": "2025-12-08T10:00:00Z",
        "created_by": {
          "id": "uuid",
          "name": "张三"
        }
      }
    ],
    "pagination": {
      "total": 1250,
      "page": 1,
      "page_size": 50,
      "total_pages": 25
    },
    "stats": {
      "total_size_bytes": 5368709120,
      "file_type_distribution": {
        "pdf": 800,
        "docx": 350,
        "xlsx": 100
      }
    }
  }
}
```

---

### 7.4 文件上传

#### 7.4.1 直接上传 (小文件 < 100MB)

```http
POST /api/v1/files/upload
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

##### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| `file` | File | ✅ | 上传文件 |
| `path` | string | ❌ | 目标路径，默认 `/` |
| `tags` | string[] | ❌ | 标签列表 |
| `auto_ingest` | boolean | ❌ | 是否自动摄取到 KB |
| `kb_name` | string | ❌ | 目标知识库 (auto_ingest=true 时必填) |

##### 响应

```json
{
  "code": 0,
  "data": {
    "file_id": "uuid",
    "name": "合同模板.pdf",
    "path": "/legal/contracts/合同模板.pdf",
    "size_bytes": 1048576,
    "oss_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",
    "ingest_task_id": "uuid"  // 如果 auto_ingest=true
  }
}
```

#### 7.4.2 OSS 直传 (大文件 - 预签名 URL)

##### Step 1: 获取预签名 URL

```http
POST /api/v1/files/upload/presign
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "filename": "large_document.pdf",
  "file_size": 1073741824,  // 1GB
  "content_type": "application/pdf",
  "path": "/legal/archives",
  "parts": 10  // 分片数量 (可选，用于分片上传)
}
```

##### 响应

```json
{
  "code": 0,
  "data": {
    "upload_id": "uuid",
    "method": "multipart",  // direct | multipart
    "oss_key": "channel-xxx/legal/archives/uuid.pdf",
    "presigned_urls": [
      {
        "part_number": 1,
        "url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...?Signature=...",
        "expires_at": "2025-12-08T13:00:00Z"
      },
      {
        "part_number": 2,
        "url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...?Signature=..."
      }
    ],
    "complete_url": "/api/v1/files/upload/complete",
    "expires_in": 3600
  }
}
```

##### Step 2: 前端直接上传到 OSS

```javascript
// 前端代码示例
for (const part of presignedUrls) {
  await fetch(part.url, {
    method: 'PUT',
    body: fileSlice,
    headers: { 'Content-Type': 'application/pdf' }
  });
}
```

##### Step 3: 完成上传

```http
POST /api/v1/files/upload/complete
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "upload_id": "uuid",
  "parts": [
    {"part_number": 1, "etag": "\"d41d8cd98f00b204e9800998ecf8427e\""},
    {"part_number": 2, "etag": "\"098f6bcd4621d373cade4e832627b4f6\""}
  ],
  "auto_ingest": true,
  "kb_name": "regulations"
}
```

---

### 7.5 文件下载

#### 获取下载链接

```http
GET /api/v1/files/{file_id}/download
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 响应

```json
{
  "code": 0,
  "data": {
    "download_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...?Signature=...",
    "filename": "合同模板.pdf",
    "file_size": 1048576,
    "expires_in": 3600,
    "expires_at": "2025-12-08T13:00:00Z"
  }
}
```

#### 批量下载 (打包)

```http
POST /api/v1/files/download/batch
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "file_ids": ["uuid1", "uuid2", "uuid3"],
  "format": "zip"  // zip | tar.gz
}
```

##### 响应 (异步任务)

```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "processing",
    "poll_url": "/api/v1/files/download/batch/{task_id}"
  }
}
```

---

### 7.6 文件操作

#### 移动文件

```http
POST /api/v1/files/{file_id}/move
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "target_path": "/legal/archives/2024"
}
```

#### 复制文件

```http
POST /api/v1/files/{file_id}/copy
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "target_path": "/backup/legal"
}
```

#### 重命名文件

```http
PATCH /api/v1/files/{file_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "name": "新文件名.pdf",
  "tags": ["重要", "已审核"]
}
```

#### 删除文件

```http
DELETE /api/v1/files/{file_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 批量删除

```http
POST /api/v1/files/batch/delete
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "file_ids": ["uuid1", "uuid2", "uuid3"]
}
```

---

### 7.7 RAG 系统融合

#### 7.7.1 将文件 Ingest 到知识库

```http
POST /api/v1/files/ingest
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "file_ids": ["uuid1", "uuid2", "uuid3"],
  "kb_name": "regulations",
  "strategy_config": {
    "chunking_mode": "semantic",
    "chunk_size": 800,
    "force_ocr": false
  }
}
```

##### 响应

```json
{
  "code": 0,
  "data": {
    "batch_id": "uuid",
    "tasks": [
      {"file_id": "uuid1", "task_id": "task-uuid1", "status": "pending"},
      {"file_id": "uuid2", "task_id": "task-uuid2", "status": "pending"},
      {"file_id": "uuid3", "task_id": "task-uuid3", "status": "pending"}
    ],
    "stream_url": "/api/v1/ingest/batch/{batch_id}/stream"
  }
}
```

#### 7.7.2 从现有 OSS 路径批量 Ingest

```http
POST /api/v1/files/ingest/path
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "path": "/legal/contracts/2025",
  "kb_name": "regulations",
  "recursive": true,
  "file_types": ["pdf", "docx"],
  "strategy_config": {
    "chunking_mode": "semantic"
  }
}
```

#### 7.7.3 查看文件的 RAG 状态

```http
GET /api/v1/files/{file_id}/rag-status
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 响应

```json
{
  "code": 0,
  "data": {
    "file_id": "uuid",
    "rag_status": "indexed",
    "indexed_kbs": [
      {
        "kb_name": "regulations",
        "chunk_count": 45,
        "quality_score": 0.92,
        "indexed_at": "2025-12-08T10:30:00Z"
      }
    ],
    "last_ingest": {
      "task_id": "uuid",
      "status": "completed",
      "completed_at": "2025-12-08T10:30:00Z"
    }
  }
}
```

#### 7.7.4 从知识库移除文件索引

```http
DELETE /api/v1/files/{file_id}/rag?kb_name=regulations
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

### 7.8 OSS 存储配置

#### 获取 Channel OSS 配置

```http
GET /api/v1/files/oss-config
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 响应 (Channel Admin 可见)

```json
{
  "code": 0,
  "data": {
    "provider": "aliyun_oss",
    "bucket": "omnirag-production",
    "region": "oss-cn-hangzhou",
    "prefix": "channel-uuid/",
    "storage_class": "Standard",
    "quota": {
      "total_gb": 10240,
      "used_gb": 3500,
      "remaining_gb": 6740
    },
    "lifecycle_rules": [
      {
        "name": "archive-old-files",
        "prefix": "archives/",
        "days": 365,
        "transition_to": "IA"
      }
    ]
  }
}
```

#### 更新 OSS 配置 (Super Admin)

```http
PATCH /api/v1/files/oss-config
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

##### 请求体

```json
{
  "quota_gb": 20480,
  "lifecycle_rules": [...]
}
```

---

## 8. 文档摄取 API

### 5.1 上传并摄取 (同步)

```http
POST /api/ingest/upload_run
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|:-----|:-----|:-----|:-----|
| `file` | File | ✅ | 上传文件 |
| `kb_name` | string | ✅ | 目标知识库 |
| `scenario` | string | ❌ | 预设场景 (laws/paper/table/html) |
| `strategy_config` | JSON | ❌ | 策略覆盖 |

#### 响应

```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "kb_name": "regulations",
    "file_path": "uploads/uuid_contract.pdf",
    "chunks": 150,
    "md_path": "outputs/uuid.md",
    "progress": {
      "total_chunks": 150,
      "completed_chunks": 150
    }
  }
}
```

---

### 5.2 上传并摄取 (流式 SSE)

```http
POST /api/ingest/upload_run/stream
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
Content-Type: multipart/form-data
Accept: text/event-stream
```

#### SSE 事件

```
data: {"type":"node_start","node":"loader"}

data: {"type":"node_end","node":"loader","duration_ms":150}

data: {"type":"node_start","node":"gpu_parser"}

data: {"type":"progress","data":{"total_chunks":100,"completed_chunks":45}}

data: {"type":"node_end","node":"indexer"}

data: {"type":"complete","task_id":"uuid","chunks":100}
```

---

### 5.3 获取场景预设

```http
GET /api/ingest/scenarios
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "scenarios": {
      "laws": {
        "display_name": "法律法规",
        "chunking": {"mode": "fixed", "chunk_size": 800, "chunk_overlap": 80},
        "ocr_provider": "auto",
        "force_ocr": false
      },
      "paper": {
        "display_name": "学术论文",
        "chunking": {"mode": "fixed", "chunk_size": 1200, "chunk_overlap": 120},
        "ocr_provider": "auto"
      },
      "table": {
        "display_name": "表格文档",
        "chunking": {"mode": "table_first", "chunk_size": 800},
        "ocr_provider": "auto",
        "force_ocr": true
      }
    }
  }
}
```

---

### 5.4 获取摄取任务状态

```http
GET /api/ingest/tasks/{task_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "task_id": "uuid",
    "status": "completed",  // pending, processing, completed, failed
    "kb_name": "regulations",
    "filename": "contract.pdf",
    "progress": {
      "stage": "finalize",
      "total_chunks": 150,
      "completed_chunks": 150
    },
    "quality_metrics": {
      "avg_quality": 0.92,
      "dedup_rate": 0.05
    },
    "error": null,
    "created_at": "2025-12-08T10:00:00Z",
    "completed_at": "2025-12-08T10:02:30Z"
  }
}
```

---

## 6. 聊天 API

### 6.1 创建聊天会话

```http
POST /api/chat/sessions
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "name": "合同法咨询",
  "kb_names": ["regulations", "cases"],
  "config": {
    "top_k": 10,
    "temperature": 0.1,
    "rerank_threshold": 0.5,
    "web_search_enabled": false
  }
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "合同法咨询",
    "kb_names": ["regulations", "cases"],
    "config": { ... },
    "created_at": "2025-12-08T12:00:00Z"
  }
}
```

---

### 6.2 获取会话列表

```http
GET /api/chat/sessions?page=1&page_size=20
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

### 6.3 获取会话详情

```http
GET /api/chat/sessions/{session_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "id": "uuid",
    "name": "合同法咨询",
    "kb_names": ["regulations", "cases"],
    "config": { ... },
    "messages": [
      {
        "id": "uuid",
        "role": "user",
        "content": "什么是合同的生效要件？",
        "timestamp": "2025-12-08T12:00:00Z"
      },
      {
        "id": "uuid",
        "role": "assistant",
        "content": "根据《民法典》...",
        "citations": [...],
        "timestamp": "2025-12-08T12:00:05Z"
      }
    ]
  }
}
```

---

### 6.4 发送消息 (流式 SSE)

```http
POST /api/chat/sessions/{session_id}/stream
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
Accept: text/event-stream
```

#### 请求体

```json
{
  "query": "什么是合同的生效要件？",
  "config_override": {
    "top_k": 15,
    "temperature": 0.2
  }
}
```

#### SSE 事件流

```
event: phase
data: {"type":"phase","name":"preprocessor","status":"start"}

event: phase
data: {"type":"phase","name":"retriever","status":"start"}

event: phase
data: {"type":"phase","name":"reranker","status":"end"}

event: answer
data: {"type":"answer","delta":"根据"}

event: answer
data: {"type":"answer","delta":"《民法典》"}

event: citation
data: {"type":"citation","doc_id":"uuid","page":15,"bbox":[100,200,500,300],"content":"合同生效需要..."}

event: final
data: {"type":"final","answer":"根据《民法典》...","citations":[...],"confidence":0.92}
```

---

### 6.5 发送消息 (非流式)

```http
POST /api/chat/sessions/{session_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "query": "什么是合同的生效要件？"
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "message_id": "uuid",
    "answer": "根据《民法典》第502条...",
    "citations": [
      {
        "doc_id": "uuid",
        "filename": "civil_code.pdf",
        "page": 15,
        "bbox": [100, 200, 500, 300],
        "content": "合同生效需要当事人具有相应的民事行为能力..."
      }
    ],
    "confidence": 0.92,
    "metrics": {
      "retrieval_time_ms": 150,
      "rerank_time_ms": 80,
      "generation_time_ms": 1200
    }
  }
}
```

---

### 6.6 更新会话

```http
PATCH /api/chat/sessions/{session_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

### 6.7 删除会话

```http
DELETE /api/chat/sessions/{session_id}
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

---

## 7. 检索 API

### 7.1 向量检索

```http
POST /api/retrieval/search
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "query": "合同生效要件",
  "kb_names": ["regulations", "cases"],
  "top_k": 20,
  "candidate_k": 100,
  "vector_weight": 0.6,
  "keyword_weight": 0.4,
  "filters": {
    "block_type": "text",
    "language": "zh"
  },
  "rerank": true
}
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "results": [
      {
        "chunk_id": "uuid",
        "doc_id": "uuid",
        "content": "合同生效需要当事人具有相应的民事行为能力...",
        "score": 0.92,
        "rerank_score": 0.88,
        "metadata": {
          "filename": "civil_code.pdf",
          "page_num": 15,
          "bbox": [100, 200, 500, 300],
          "block_type": "text"
        }
      }
    ],
    "total": 50,
    "metrics": {
      "vector_results": 100,
      "keyword_results": 80,
      "fused_results": 50,
      "retrieval_time_ms": 150
    }
  }
}
```

---

### 7.2 获取 Collection 信息

```http
GET /api/retrieval/collections
X-Channel-ID: <channel_id>
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "collections": [
      {
        "name": "kb_legal_regulations_v1",
        "kb_name": "regulations",
        "vector_count": 125000,
        "disk_size_mb": 8500,
        "dimension": 1024
      }
    ]
  }
}
```

---

## 8. 配置 API

### 8.1 获取 Provider 列表

```http
GET /api/config/providers
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "providers": [
      {
        "id": "uuid",
        "name": "dashscope",
        "display_name": "阿里云灵积",
        "category": "llm",
        "is_active": true,
        "models": [
          {
            "id": "uuid",
            "model_id": "qwen-plus",
            "name": "Qwen Plus",
            "type": "chat",
            "is_default": true
          }
        ]
      }
    ]
  }
}
```

---

### 8.2 创建 Provider (管理员)

```http
POST /api/config/providers
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "name": "openai",
  "display_name": "OpenAI",
  "category": "llm",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-xxx",
  "channel_id": null,  // null = 全局可用
  "is_active": true
}
```

---

### 8.3 创建模型配置

```http
POST /api/config/models
Authorization: Bearer <token>
```

#### 请求体

```json
{
  "provider_id": "uuid",
  "model_id": "gpt-4o",
  "name": "GPT-4o",
  "type": "chat",
  "parameters": {
    "max_tokens": 4096,
    "temperature": 0.7
  },
  "is_default": false
}
```

---

### 8.4 获取运行时配置

```http
GET /api/config/runtime
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "default_chunk_size": 512,
    "default_chunk_overlap": 50,
    "default_top_k": 10,
    "max_file_size_mb": 100,
    "supported_file_types": ["pdf", "docx", "pptx", "xlsx", "md", "html", "txt"],
    "ocr_providers": ["auto", "qwen-vl", "deepseek", "paddle"],
    "chunking_modes": ["fixed", "semantic", "layout_aware", "table_first"]
  }
}
```

---

## 9. 系统 API

### 9.1 健康检查

```http
GET /api/health
```

#### 响应

```json
{
  "app_up": true,
  "postgres_connected": true,
  "qdrant_connected": true,
  "es_connected": true,
  "redis_connected": true,
  "blob_available": true
}
```

---

### 9.2 Prometheus 指标

```http
GET /api/metrics
Authorization: Bearer <token>
```

返回 Prometheus 格式的指标数据。

---

### 9.3 运行时指标

```http
GET /api/metrics/runtime
Authorization: Bearer <token>
```

#### 响应

```json
{
  "code": 0,
  "data": {
    "uploads_total": 15000,
    "uploads_success": 14850,
    "uploads_failed": 150,
    "sse_active_connections": 25,
    "cache": {
      "embedding_cache_size": 8500,
      "semantic_cache_hit_rate": 0.35
    },
    "rate_limit": {
      "enabled": true,
      "backend": "redis"
    }
  }
}
```

---

## 10. SSE 事件规范

### 10.1 事件类型

| 事件类型 | 说明 |
|:---------|:-----|
| `phase` | 阶段开始/结束 |
| `answer` | 增量回答内容 |
| `citation` | 引用信息 |
| `final` | 最终结果 |
| `progress` | 进度更新 |
| `error` | 错误信息 |
| `ping` | 心跳 (每 30s) |

### 10.2 事件格式

```typescript
interface PhaseEvent {
  type: "phase";
  name: string;  // preprocessor, retriever, reranker, generator
  status: "start" | "end" | "fallback";
  duration_ms?: number;
}

interface AnswerEvent {
  type: "answer";
  delta: string;
}

interface CitationEvent {
  type: "citation";
  doc_id: string;
  page: number;
  bbox?: [number, number, number, number];
  content: string;
}

interface FinalEvent {
  type: "final";
  answer: string;
  citations: Citation[];
  confidence: number;
  metrics?: {
    chars: number;
    words: number;
    chars_per_sec: number;
  };
}

interface ProgressEvent {
  type: "progress";
  data: {
    stage: string;
    total_chunks: number;
    completed_chunks: number;
  };
}

interface ErrorEvent {
  type: "error";
  code: number;
  message: string;
}

interface PingEvent {
  type: "ping";
  ts: number;  // timestamp in ms
}
```

---

## 11. 错误码定义

### 11.1 通用错误 (1xxxx)

| Code | Message |
|:-----|:--------|
| 10001 | Internal server error |
| 10002 | Service unavailable |
| 10003 | Request timeout |
| 10004 | Rate limit exceeded |

### 11.2 认证错误 (2xxxx)

| Code | Message |
|:-----|:--------|
| 20001 | Unauthorized |
| 20002 | Token expired |
| 20003 | Invalid token |
| 20004 | Insufficient permissions |
| 20005 | User not found |
| 20006 | Invalid credentials |

### 11.3 资源错误 (3xxxx)

| Code | Message |
|:-----|:--------|
| 30001 | Channel not found |
| 30002 | Knowledge base not found |
| 30003 | Document not found |
| 30004 | Session not found |

### 11.4 业务错误 (4xxxx)

| Code | Message |
|:-----|:--------|
| 40001 | Email already registered |
| 40002 | Invalid email format |
| 40003 | Password too weak |
| 40004 | KB name already exists |
| 40005 | File type not supported |
| 40006 | File too large |
| 40007 | Ingest failed |
| 40008 | Retrieval failed |

### 11.5 外部服务错误 (5xxxx)

| Code | Message |
|:-----|:--------|
| 50001 | LLM service unavailable |
| 50002 | Embedding service unavailable |
| 50003 | Vector store unavailable |
| 50004 | OCR service unavailable |

---

## 12. Database Schema

### 12.1 ER 图

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│      User       │       │     Channel     │       │   KnowledgeBase │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id              │       │ id              │       │ id              │
│ email           │       │ name            │       │ channel_id  ────┼───┐
│ password_hash   │       │ display_name    │       │ name            │   │
│ name            │       │ description     │       │ display_name    │   │
│ phone           │       │ config (JSON)   │       │ config (JSON)   │   │
│ role            │       │ is_active       │       │ created_at      │   │
│ is_active       │       │ created_at      │       │ updated_at      │   │
│ created_at      │       └────────┬────────┘       └─────────────────┘   │
│ last_login_at   │                │                                      │
└────────┬────────┘                │                                      │
         │                         │                                      │
         │    ┌────────────────────┼──────────────────────────────────────┘
         │    │                    │
         │    │                    │
         ▼    ▼                    ▼
┌─────────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   ChannelMember     │   │   ChatSession   │   │    Document     │
├─────────────────────┤   ├─────────────────┤   ├─────────────────┤
│ id                  │   │ id              │   │ id              │
│ channel_id      ────┼───┤ channel_id  ────┼───┤ kb_id       ────┼───┐
│ user_id         ────┼───┤ user_id     ────┼───┤ filename        │   │
│ role                │   │ name            │   │ file_type       │   │
│ created_at          │   │ config (JSON)   │   │ file_size       │   │
└─────────────────────┘   │ created_at      │   │ page_count      │   │
                          │ updated_at      │   │ chunk_count     │   │
                          └────────┬────────┘   │ status          │   │
                                   │            │ quality_score   │   │
                                   │            │ blob_path       │   │
                                   ▼            │ created_at      │   │
                          ┌─────────────────┐   └─────────────────┘   │
                          │ SessionKBLink   │                         │
                          ├─────────────────┤                         │
                          │ session_id  ────┼───┐                     │
                          │ kb_id       ────┼─┐ │                     │
                          │ priority        │ │ │                     │
                          └─────────────────┘ │ │                     │
                                              │ │                     │
                                              ▼ ▼                     │
                                    ┌─────────────────┐               │
                                    │   ChatMessage   │               │
                                    ├─────────────────┤               │
                                    │ id              │               │
                                    │ session_id  ────┼───────────────┘
                                    │ role            │
                                    │ content         │
                                    │ citations (JSON)│
                                    │ created_at      │
                                    └─────────────────┘
```

### 12.2 表结构定义

#### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'user',  -- admin, user
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX idx_users_email ON users(email);
```

#### channels

```sql
CREATE TABLE channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT name_format CHECK (name ~* '^[a-z][a-z0-9_]*$')
);

CREATE INDEX idx_channels_name ON channels(name);
```

#### channel_members

```sql
CREATE TABLE channel_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member',  -- admin, member, viewer
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, user_id)
);

CREATE INDEX idx_channel_members_user ON channel_members(user_id);
CREATE INDEX idx_channel_members_channel ON channel_members(channel_id);
```

#### knowledge_bases

```sql
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, name),
    CONSTRAINT name_format CHECK (name ~* '^[a-z][a-z0-9_]*$')
);

CREATE INDEX idx_kb_channel ON knowledge_bases(channel_id);
```

#### documents

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_size BIGINT NOT NULL,
    page_count INTEGER,
    chunk_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
    quality_score FLOAT,
    blob_path VARCHAR(500) NOT NULL,
    doc_metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_documents_kb ON documents(kb_id);
CREATE INDEX idx_documents_status ON documents(status);
```

#### chat_sessions

```sql
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100),
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_sessions_channel ON chat_sessions(channel_id);
```

#### session_kb_links

```sql
CREATE TABLE session_kb_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 0,

    UNIQUE(session_id, kb_id)
);

CREATE INDEX idx_session_kb_session ON session_kb_links(session_id);
```

#### chat_messages

```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    citations JSONB DEFAULT '[]',
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON chat_messages(session_id);
CREATE INDEX idx_messages_created ON chat_messages(created_at);
```

#### providers

```sql
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID REFERENCES channels(id) ON DELETE CASCADE,  -- NULL = global
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    category VARCHAR(20) NOT NULL,  -- llm, embedding, reranker, ocr
    base_url VARCHAR(500),
    api_key_encrypted BYTEA,  -- AES encrypted
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, name, category)
);

CREATE INDEX idx_providers_category ON providers(category);
```

#### model_configs

```sql
CREATE TABLE model_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_id VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL,  -- chat, embedding, rerank
    parameters JSONB DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(provider_id, model_id)
);

CREATE INDEX idx_models_provider ON model_configs(provider_id);
CREATE INDEX idx_models_type ON model_configs(type);
```

```sql
CREATE TABLE ingest_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    file_id UUID REFERENCES files(id) ON DELETE SET NULL,  -- 关联文件管理
    batch_id UUID NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    stage VARCHAR(20),
    progress JSONB DEFAULT '{}',
    quality_metrics JSONB DEFAULT '{}',
    error_log JSONB DEFAULT '[]',
    strategy_config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tasks_status ON ingest_tasks(status);
CREATE INDEX idx_tasks_kb ON ingest_tasks(kb_id);
CREATE INDEX idx_tasks_file ON ingest_tasks(file_id);
```

#### files (OSS 文件管理)

```sql
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,

    -- 文件信息
    name VARCHAR(500) NOT NULL,
    path VARCHAR(1000) NOT NULL,  -- 虚拟路径 /legal/contracts/xxx.pdf
    oss_key VARCHAR(1000) NOT NULL,  -- OSS 实际路径
    oss_bucket VARCHAR(100) NOT NULL,

    -- 文件属性
    size_bytes BIGINT NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    mime_type VARCHAR(100),
    checksum_md5 VARCHAR(32),
    checksum_sha256 VARCHAR(64),

    -- 元数据
    tags TEXT[] DEFAULT '{}',
    file_metadata JSONB DEFAULT '{}',

    -- RAG 关联状态
    rag_status VARCHAR(20) DEFAULT 'none',  -- none, pending, indexed, failed
    indexed_kbs TEXT[] DEFAULT '{}',  -- 已索引的知识库列表

    -- 审计
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE,  -- 软删除

    UNIQUE(channel_id, path)
);

CREATE INDEX idx_files_channel ON files(channel_id);
CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_files_rag_status ON files(rag_status);
CREATE INDEX idx_files_type ON files(file_type);
CREATE INDEX idx_files_tags ON files USING GIN(tags);
CREATE INDEX idx_files_created_at ON files(created_at);
```

#### folders (文件夹 - 可选虚拟目录)

```sql
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    path VARCHAR(1000) NOT NULL,  -- 完整路径
    parent_path VARCHAR(1000),    -- 父路径
    folder_metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(channel_id, path)
);

CREATE INDEX idx_folders_channel ON folders(channel_id);
CREATE INDEX idx_folders_parent ON folders(parent_path);
```

#### file_kb_links (文件-知识库关联)

```sql
CREATE TABLE file_kb_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    chunk_count INTEGER DEFAULT 0,
    quality_score FLOAT,
    indexed_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(file_id, kb_id)
);

CREATE INDEX idx_file_kb_file ON file_kb_links(file_id);
CREATE INDEX idx_file_kb_kb ON file_kb_links(kb_id);
```

#### api_keys (API 密钥)

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 密钥信息
    name VARCHAR(100) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,  -- 显示用: omni_sk_xxxx
    key_hash VARCHAR(64) NOT NULL,    -- SHA256 hash

    -- 权限
    scopes TEXT[] NOT NULL,           -- ['kb:read', 'chat:write']
    channel_ids UUID[],               -- NULL = 继承用户权限

    -- 生命周期
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(key_hash)
);

CREATE INDEX idx_api_keys_user ON api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_active ON api_keys(is_active) WHERE is_active = TRUE;
```

#### upload_sessions (分片上传会话)

```sql
CREATE TABLE upload_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 上传信息
    filename VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    content_type VARCHAR(100),
    target_path VARCHAR(1000) NOT NULL,
    oss_key VARCHAR(1000) NOT NULL,
    oss_upload_id VARCHAR(500),  -- OSS 分片上传 ID

    -- 状态
    status VARCHAR(20) DEFAULT 'pending',  -- pending, uploading, completing, completed, failed
    parts_total INTEGER,
    parts_completed INTEGER DEFAULT 0,
    parts_info JSONB DEFAULT '[]',  -- [{part_number, etag, size}]

    -- 配置
    auto_ingest BOOLEAN DEFAULT FALSE,
    kb_name VARCHAR(50),
    strategy_config JSONB,

    -- 时间
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_upload_sessions_user ON upload_sessions(user_id);
CREATE INDEX idx_upload_sessions_status ON upload_sessions(status);
CREATE INDEX idx_upload_sessions_expires ON upload_sessions(expires_at);
```

### 12.3 Row Level Security (RLS)

```sql
-- 启用 RLS
ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- 知识库访问策略
CREATE POLICY kb_access ON knowledge_bases
    USING (
        channel_id IN (
            SELECT channel_id FROM channel_members
            WHERE user_id = current_setting('app.current_user_id')::uuid
        )
    );

-- 文档访问策略
CREATE POLICY doc_access ON documents
    USING (
        kb_id IN (
            SELECT kb.id FROM knowledge_bases kb
            JOIN channel_members cm ON kb.channel_id = cm.channel_id
            WHERE cm.user_id = current_setting('app.current_user_id')::uuid
        )
    );

-- 会话访问策略
CREATE POLICY session_access ON chat_sessions
    USING (user_id = current_setting('app.current_user_id')::uuid);
```

---

## 附录: Pydantic Schema 示例

```python
# server/schemas.py
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserResponse


class KBCreate(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str
    description: Optional[str] = None
    config: Optional[dict] = None


class KBResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    description: Optional[str]
    config: dict
    doc_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatCreate(BaseModel):
    query: str = Field(..., min_length=1)
    config_override: Optional[dict] = None


class CitationResponse(BaseModel):
    doc_id: UUID
    filename: str
    page: Optional[int]
    bbox: Optional[List[float]]
    content: str


class ChatResponse(BaseModel):
    message_id: UUID
    answer: str
    citations: List[CitationResponse]
    confidence: float
```

---

*本文档基于 `docs/tech/system-design.md` 和 `docs/architecture.md` 生成，如有冲突以 system-design.md 为准。*
