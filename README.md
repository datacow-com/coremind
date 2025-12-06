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
  - 可选：安装 pre-push 钩子：`pre-commit install --hook-type pre-push`
  - 手动运行：`pre-commit run --all-files`
  - Python 使用 ruff/mypy/bandit；前端使用 `npm run lint` 与 `npm run type-check`。
  - 详细规范见：`docs/coding-standards.md`

## 快速开始（本地）

- 启动后端与前端：`make dev`（后端端口默认 `8000`，前端端口见 `scripts/dev.sh`）
- 仅启动后端：`python3 -m uvicorn server.main:app --port 8000 --reload`
- 运行全部测试：`pytest -q`
- 端到端测试（轻量模式）：
  - 使用本地地址：`E2E_BASE_URL=http://127.0.0.1:8000 pytest -q -k 'e2e'`
  - 说明：在未设置 `DATABASE_URL` 时，后端自动进入轻量内存模式，所有 API 可用且 e2e 场景通过。
  - 可选：启用语义分块 `SEMANTIC_CHUNKING=1`
  - 可选：启用 Cohere Rerank：设置 `COHERE_API_KEY` 与 `COHERE_RERANK_MODEL`

## Docker 端到端与数据库初始化

- 启动完整栈并运行 e2e：`make e2e-docker`
  - 组件：Nginx、Backend、Postgres、Milvus、Frontend
  - e2e 基于 `http://localhost:3500`，结束自动清理栈
- 初始化数据库（本地 DB 模式）：
  - 设置 `DATABASE_URL` 后运行：`make db-init`
  - 说明：调用 ORM 的 `init_db_sync()` 创建/更新表结构

## 开发者 FAQ 与问题定位

- e2e 默认连接 3500，如本地仅后端运行请设置 `E2E_BASE_URL`
- CI pre-commit 执行前后端静态检查与格式化，失败可用 `make fix` 修复并重试
- 密钥泄漏扫描：CI 将运行 Gitleaks，必要时自定义规则见 `.gitleaks.toml`
- Milvus 性能验证：`make milvus-bench`（需要可用的 Milvus 服务和网络）
- 模型接入：
  - Cohere Rerank：设置 `COHERE_API_KEY` 与 `COHERE_RERANK_MODEL`
  - YOLO 布局检测：设置 `YOLO_ENABLED=1` 与 `YOLO_MODEL=/path/to/best.pt`（可选，未安装时自动降级）
  - LayoutLMv3 版面解析：设置 `LAYOUTLM_ENABLED=1` 与 `LAYOUTLM_MODEL=microsoft/layoutlmv3-base`（可选，未安装时自动降级）
  - LayoutLMv3 块分类（可选）：设置 `LAYOUTLM_CLASS_MODEL=<hf_model_with_id2label>` 用于块类型细分（paragraph/heading/table/figure）
  - 聊天模型：
    - OpenAI：`OPENAI_API_KEY` 与 `OPENAI_CHAT_MODEL`
    - Gemini：`GEMINI_API_KEY` 与 `GEMINI_CHAT_MODEL`
    - Anthropic：`ANTHROPIC_API_KEY` 与 `ANTHROPIC_CHAT_MODEL`
    - DeepSeek：`DEEPSEEK_API_KEY` 与 `DEEPSEEK_CHAT_MODEL`
    - OpenRouter：`OPENROUTER_API_KEY` 与 `OPENROUTER_CHAT_MODEL`
    - Ollama：`OLLAMA_URL` 与 `OLLAMA_MODEL`

## 本地下载模型（Mac ARM/M4 支持）

- 一键下载：`make models`
  - 下载 YOLOv8n 权重到 `models/yolo/yolov8n.pt`
  - 缓存 LayoutLMv3 到 `models/hf/microsoft/layoutlmv3-base`
- 配置示例：
  - `export YOLO_ENABLED=1`
  - `export YOLO_MODEL=models/yolo/yolov8n.pt`
  - `export LAYOUTLM_ENABLED=1`
  - `export LAYOUTLM_MODEL=microsoft/layoutlmv3-base`
  - `export LAYOUTLM_CLASS_MODEL=nielsr/layoutlmv3-finetuned-funsd`

## 解析评估与报告

- 混合检索评估：`make eval`（需准备 `data/samples/queries.jsonl`）
- 布局分类评估：
  - 下载分类模型：`make models-class`
  - 运行评估：`LAYOUTLM_CLASS_MODEL=nielsr/layoutlmv3-finetuned-funsd make eval-layoutlm`
  - 报告输出：`reports/layoutlm_eval.json`（包含块数量与类型分布）

## 常用命令（Makefile）

- `make setup`：安装依赖并安装 pre-commit 钩子
- `make check`：运行所有 pre-commit 钩子
- `make push-check`：运行 pre-push 钩子
- `make lint` / `make format` / `make fix`：代码质量检查与修复
- `make type`：类型检查（Python/前端）
- `make coverage`：覆盖率报告
