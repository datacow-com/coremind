## 联调目标

- 验证后端受保护与公开接口可用（鉴权、摄取、版本化、Dashboard）。
- 验证 Nginx 反代路径与端口（3500~）映射正确。
- 输出可视化验收结果：HTTP 状态码、关键 JSON 字段、异常日志摘要。

## 前置环境

- 容器已启动：postgres(3504)、milvus(3505/3506)、backend(3503)、frontend(3502)、nginx(3500)。
- `.env` 已含各 Provider 的 API Key；可使用 `POST /api/auth/demo` 获取 token。

## 联调步骤

### 1. 鉴权链路

- 生成 Demo Token：`POST http://localhost:3500/api/auth/demo`
- 记录响应 `access_token`，后续请求携带 `Authorization: Bearer <token>`。

### 2. 模型网关相关

- Dashboard：`GET http://localhost:3500/api/models/dashboard/stats`（Bearer）
  - 期望字段：`total_models, active_models, cn_models, overseas_models, avg_ttft, avg_throughput, avg_error_rate`
- Providers 列表：`GET http://localhost:3500/api/models?search=&page=1&page_size=20`（Bearer）
  - 期望字段：`models[], total, page, page_size`
- 创建 Provider：`POST http://localhost:3500/api/models/`（Bearer）
  - Body 示例：`{"name":"qwen-plus","stack":"cn","category":"llm","endpoint":"https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions","priority":1}`
  - 期望：返回新 Provider JSON，后续列表出现。
- 测试连通：`POST http://localhost:3500/api/models/{id}/test`（Bearer）
  - 期望：返回 `ttft/throughput` 数值，异常时给出错误说明。

### 3. 环境版本化

- 列版本：`GET http://localhost:3500/api/models/environments/dev/versions`（Bearer）
- 预览应用：`POST http://localhost:3500/api/models/environments/dev/versions/{version}/apply?dry_run=true`（Bearer）
  - 期望：返回 `preview:{ from,to,changes }`
- 确认应用：`POST ...?dry_run=false`（Bearer）
  - 期望：返回 `applied` 与审计写入成功。

### 4. 凭据管理（示例）

- 列出凭据：`GET http://localhost:3500/api/models/{provider_id}/credentials`（Bearer）
- 保存凭据：`POST http://localhost:3500/api/models/{provider_id}/credentials/dev`（Bearer）
  - 示例：`{"auth_type":"api_key","key_name":"dashscope","rate_limit_rps":10}`
  - 期望：列表中出现该环境凭据。

### 5. 视觉摄取

- 上传 PDF：`POST http://localhost:3500/api/ingest/pdf`（form-data：`file=@sample.pdf`）
  - 期望：返回 `md` 与 `md_path`；若无 OpenAI 视觉能力，返回占位 Markdown。

### 6. 反代与健康

- 健康检查：`GET http://localhost:3500/api/health`
  - 期望：`app_up=true`，`postgres_connected=true`，`milvus_connected`可为 `false`（未使用时）。

## 结果记录与输出

- 为每一步记录：HTTP 状态码、主要 JSON 字段、失败时的错误信息与容器日志摘要。
- 汇总通过/失败项，给出修复建议（接口、配置、端口或密钥问题）。

## 风险与回退

- 若某 Provider 真实连通受限，先记录降级占位数据并标注原因（配额、地域或模型名）。
- 发现 5xx 或 502，优先检查后端容器日志与 Nginx upstream；必要时重启单一服务并重试。

请确认上述计划；确认后我将按步骤执行并回传详细验收结果。
