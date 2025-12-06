# OmniRAG 代码规范与质量门禁

## 总则

- 所有新增与修改代码必须通过本仓库的质量门禁：`pre-commit`、`ruff`、`mypy`、`bandit`、测试与 CI。
- 默认 Python 版本 `3.11`；行宽 `100`；统一双引号；禁用 `print`，使用 `logging`。
- 禁止提交任何凭据、密钥或敏感信息；默认开启密钥扫描（Gitleaks）。

## Python 风格与 Ruff

- 规则来源：`ruff.toml`（`E,F,W,I,B,UP,S`），行宽 100，目标版本 py311。
- 导入规范：
  - 分组顺序：标准库 → 第三方 → 项目内；使用 `isort` 兼容的自动排序（由 ruff 完成）。
  - 禁止未使用导入与重复导入；尽量使用显式导入而非通配符。
- 语法与现代化：
  - 使用 `match/case` 与类型标注的现代特性；避免过时写法（`UP` 规则集）。
  - 避免裸 `except`；异常处理需最小化捕获范围并保留上下文。
- 异步与 IO：
  - 节点函数使用 `async def`；避免阻塞 IO（优先 `httpx.AsyncClient`）。
  - 流式输出遵循 SSE 结构，保留心跳与阶段事件，不在流中输出非结构化内容。

## 类型检查（mypy）

- 必须为所有新函数与公共接口提供类型标注；尽量避免 `Any`。
- 使用 `TypedDict` 定义 `LangGraph` 的 State；避免动态字典滥用。
- `Optional` 显式处理；避免隐式可选（`no_implicit_optional = True`）。
- 谨慎使用 `cast` 与 `type: ignore`；如必须，添加最小范围并保留原因。
- Pydantic v2：使用 `ConfigDict(from_attributes=True)`；禁止 v1 `Config` 风格。

## 安全（Bandit）

- 禁止使用 `eval/exec`、`pickle.loads`（不可信数据）；谨慎使用 `yaml.load`（仅 `safe_load`）。
- 网络与命令：默认启用 SSL 校验；不直接拼接外部输入到命令行；禁止 `shell=True`。
- 文件与路径：使用 `pathlib/Tempfile` 等安全接口；严禁目录遍历与不受控写入。
- 隐私与凭据：不记录敏感信息到日志；使用环境变量或密钥管理；本地存储需脱敏处理。

## 模型与解析管线

- 视觉解析默认走轻量管线，依据复杂度评分自动启用 VLM；复杂场景可开启 YOLO/LayoutLM。
- 可选模型的启用依赖显式环境变量：
  - Cohere Rerank：`COHERE_API_KEY` 与 `COHERE_RERANK_MODEL`。
  - YOLO：`YOLO_ENABLED=1` 与 `YOLO_MODEL=/path/to/best.pt`。
  - LayoutLMv3：`LAYOUTLM_ENABLED=1` 与 `LAYOUTLM_MODEL`。
- 回退策略：模型不可用或未配置时，必须自动降级，保证功能不中断。

## 错误处理与日志

- 中间层返回统一的错误结构；避免泄露内部异常细节到用户端。
- 使用 `logging`（模块级 logger）；区分 `info/warning/error`；不使用 `print`。
- 仅在必要时捕获异常；保留 `traceback` 并在上层按需转换为业务错误。

## 测试与 CI

- 单测与集成测试必须覆盖新增路径；允许 `tests/**` 下的更宽松安全规则（见 `ruff.toml`）。
- 端到端：本地轻量（`E2E_BASE_URL=http://127.0.0.1:8000`）、容器栈（`make e2e-docker`）。
- UI 冒烟：Playwright 测试包含关键路径（上传→摄取→引用高亮与自动滚动）。
- 覆盖率在 CI 自动生成与上传；新增模块应补充基本覆盖。

## 提交流程（pre-commit）

- 安装：`pre-commit install`；可选 `pre-commit install --hook-type pre-push`。
- 本地运行：`pre-commit run --all-files`；修复格式与静态问题后再提交。
- 常用 Make 命令：`make check`、`make fix`、`make lint`、`make type`、`make coverage`。

## 代码组织与约定

- 目录：
  - `core/**`：检索、解析、LLM 与工具；
  - `server/**`：API 路由、服务与模型网关；
  - `frontend/**`：UI 与端到端测试；
  - `scripts/**`：基准、工具与运维脚本；
  - `docs/**`：文档与规范。
- 命名：统一驼峰/下划线风格；避免缩写不明的名称；接口参数命名必须含义清晰。
- 依赖：仅在确有必要时引入第三方库；可选依赖必须具备降级通道。

## 迁移与发布

- 数据库模式：提供初始化与迁移校验；在 CI 验证一致性与回滚路径。
- 向量与搜索：Milvus 性能基准与回归报告；本地默认回退本地索引。
- 发布前检查：通过所有门禁（pre-commit/CI/安全扫描/覆盖率），文档与示例齐备。
