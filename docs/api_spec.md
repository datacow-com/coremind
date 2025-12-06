# OmniRAG API 规范（P0 基线）

## 通用约定
- Base URL：`/api`
- 认证：HTTP Bearer JWT，除登录/静态资源外全部必需。无效/缺失返回 401。
- 响应 envelope（非流式）：`{ code: 0, message: "ok", data: ... }`；非 0 表示错误。
- 错误码：4xx 业务输入/权限/限流，429 限流，5xx 系统异常。`message` 为人类可读提示，`data` 可选包含 detail。
- 请求 ID：后端在日志中记录 `request_id`，如在 header 中提供则复用。

## 流式（SSE/NDJSON）
- Header：`Content-Type: text/event-stream`。
- 事件格式（data 行内 JSON）：
  - `{"type":"phase","name":"retrieve|rerank|generate|...","status":"start|end|fallback","request_id":""}`
  - `{"type":"answer","delta":"..."}` 增量内容
  - `{"type":"final","answer":"...","sources":[...],"conversation_id":""}`
  - `{"type":"citation", "doc_id":"", "page":1, "bbox":{}, "chunk_id":""}`
  - `{"type":"metrics","chars":...,"words":...,"chars_per_sec":...}`
  - `{"type":"error","message":"...","code":429|500}`
  - 心跳：`event: ping` + `data: {"ts": <ms>}`

## 主要接口
- 认证：`POST /auth/login`（自备 JWT 或网关颁发，当前前端粘贴 token）。
- 聊天：
  - `POST /chat/stream` SSE，入参：`query, kb_name?, top_k?, candidate_k?, vector_weight?, keyword_weight?, web_search_enabled?`
  - `POST /chat` 非流式，同上。
  - `GET /chat/sessions` 列出会话（包含 kb 绑定与配置）；`POST /chat/sessions` 创建；`PATCH /chat/sessions/{id}` 更新；`DELETE /chat/sessions/{id}` 删除
- 文档：
  - `GET /documents` 列表；`DELETE /documents/{id}`；`GET /documents/{id}/download`
  - 摄取：`POST /ingest/{type}` 与 `/ingest/{type}/stream`，统一文件校验；`type` 包含 pdf/image/markdown/docx/pptx/xlsx/html/eml/auto
- 知识库：
  - `GET /kb` 列表；`POST /kb/create`；`GET /kb/{name}/config`（含 `effective_config`，包括分块/挖掘策略）；`POST /kb/{name}/config`；`POST /kb/{name}/config/reset`
  - `GET /kb/{name}/documents` 文档列表
- 检索/向量：
  - `POST /vector-store/search` 入参：`query, kb_name?, top_k?, candidate_k?, weights...`
  - `GET /vector-store/collections`
- 配置/运行时：
  - `GET /config/runtime` 只读运行参数
  - `GET /metrics`（Prometheus），受 token+IP 白名单保护
  - `GET /api/metrics/runtime` 业务运行指标（见下）

## 运行时指标 `/api/metrics/runtime`
响应（envelope）：
```
{
  "code": 0,
  "message": "ok",
  "data": {
    "uploads_total": ...,
    "uploads_reject": ...,
    "uploads_scan_fail": ...,
    "sse_active": ...,
    "rate_limit": {
      "enabled": true,
      "backend": "redis|memory"
    },
    "web_search": {
      "provider": "...",
      "enabled": true
    }
  }
}
```

## 限流与熔断
- 默认在 prod 启用限流（Redis 优先，fallback 内存），429 返回。
- 外部调用（LLM/WebSearch/向量）统一重试+熔断，失败返回 502/504，并给出 message。

## 上传/安全
- 所有上传接口统一大小/类型/魔数校验，PDF 深度校验，病毒扫描可选。
- 失败返回 4xx，`message` 说明原因。
