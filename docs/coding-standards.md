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

- LangGraph 状态：使用 `TypedDict` 定义 IngestState/RetrievalState，字段与接口契约保持一致。
- 流式输出：事件仅允许结构化类型（node_start/node_end/answer/complete/citation/error/metrics）；禁止在流中输出非结构化日志。
- 策略即状态：会话/KB 的 `strategy_config` 必须可序列化、可校验（Pydantic）；前后端字段一致；默认值由后端集中定义，前端仅补齐不自创字段。
- 多模型/网关：统一走 gateway/registry，不在业务代码中直连外部大模型。
- 预览/解析：文档预览接口需返回结构化 bbox/页面信息；前端不得直接读取存储路径。

## 错误处理与日志

- 中间层返回统一的错误结构；避免泄露内部异常细节到用户端。
- 使用 `logging`（模块级 logger）；区分 `info/warning/error`；不使用 `print`。
- 仅在必要时捕获异常；保留 `traceback` 并在上层按需转换为业务错误。

## 测试与 CI

- 单测：核心节点（chunker/retriever/reranker）与 API schema 校验；类型检查（mypy）不可跳过。
- 集成/E2E：覆盖主链路（上传→摄取/索引→聊天→引用预览），包含异常场景（429/401/网络中断/SSE 断开）。
- 性能/长耗时：对流式接口（ingest/chat）做超时与断线恢复测试；大文件上传与并发 ingest 需有用例或脚本。
- CI：必须跑 ruff + mypy + tests + bandit；失败不得提交；保持 pre-commit 钩子启用。

## 提交流程（pre-commit）

- 必须启用仓库提供的 pre-commit 钩子；提交前本地通过 ruff、mypy、bandit、tests。
- 禁止跳过钩子或 `--no-verify`；如特殊情况需在 MR/PR 说明。

## 代码组织与约定

- 分层清晰：core（算法/管线）、server（API/路由）、frontend（UI）。
- 前端接口白名单：`/api/chat/run`、`/api/chat/sessions*`、`/api/kb/{kb}/documents`、`/documents/{id}/pages/{page}`、`/api/ingest/upload_run(/stream)`；禁止新增或复用废弃接口（`/api/documents*`、`/api/chat/stream`、旧 ingest 进度）。
- 兼容性：废弃接口标注 deprecated，不再新增依赖；新增接口需文档化字段与错误格式。
- 配置与默认值：统一由后端定义并暴露，前端不得硬编码私有默认。
