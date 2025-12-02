# OmniRAG

## 配置集中化与运行说明

- 使用 `.env`（参考 `.env.example`）配置：`APP_ENV`、`SECRET_KEY`、`MILVUS_URI|HOST|PORT`、`UPLOADS_DIR`、`USAGE_DIR`、`LLM_PROVIDER`、`VISION_PROVIDER`、`WEB_SEARCH_PROVIDER`、各 Provider API Key、告警阈值。
- 运行时配置只读端点：`/api/config/runtime` 展示集中化配置；`/api/system/status` 展示健康与集合信息。
- 用量与阈值：`/api/metrics/usage` 返回每日 `usage` 与聚合 `summary`；`/api/alerts/thresholds` 读写阈值（缺省值从 settings 读取）。
- Web 搜索 Provider：`/api/web/providers/status` 查看当前与可用性；`POST /api/web/providers/select` 运行时切换（不持久化）。
- 运行时设置更新：`POST /api/system/settings/update` 支持轻量运行时参数（如 `chat_temperature/vector_weight/keyword_weight`）。

## 安全与健康

- 生产强制 `SECRET_KEY`；速率限制与心跳可通过 `settings.rate_limit_enabled/rate_limit_per_minute/sse_heartbeat_interval` 控制。
- SSE 流包含 `event: ping` 心跳与阶段事件；返回 `429` 时前端给予轻提示。

## 开发与测试

- 关键测试位于 `tests/*`，包括：路由意图、聊天流、摄取、向量集合、Web 搜索、告警阈值、心跳与限流。
- GitHub Actions 在 `.github/workflows/ci.yml` 执行关键测试，保障持续集成。
- 代码质量检查（pre-commit）：
  - 安装开发依赖：`pip install -r requirements-dev.txt`
  - 安装钩子：`pre-commit install`
  - 手动运行：`pre-commit run --all-files`
  - Python 使用 ruff/mypy/bandit；前端使用 `npm run lint` 与 `npm run type-check`。
