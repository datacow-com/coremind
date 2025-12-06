# OmniRAG 测试QA标准

## 测试范围与目标
- 验证知识库基础配置与检索参数的动态生效，覆盖嵌入模型与所有下拉/数值项。
- 验证端到端摄取到检索流程在 Docker 容器环境运行。
- 验证 DashScope 嵌入端点修正与国内优先策略，禁止使用 OPENAI 嵌入。
- 验证向量后端选择与集合名按知识库覆盖（Milvus/Qdrant/Elasticsearch/本地）。
- 验证“恢复默认设置”“保存配置”操作一致性。

## 测试环境
- 统一使用 Docker 容器服务，保持开发模式端口映射：
  - 后端 API `http://localhost:3503`
  - 前端 `http://localhost:3502` 或统一入口 `http://localhost:3500`
- 启动命令：`docker compose up -d backend frontend`，按需启用 `milvus|elasticsearch|qdrant` profile。
- 验证容器来源：`curl -s http://localhost:3503/api/system/status` 应显示 `uploads_dir: /app/uploads`、`postgres/milvus` 地址。

## 测试数据
- 法律：`downloads/kb_laws.pdf`（中国宪法2018）。
- 论文：`downloads/kb_paper.pdf`（Attention is All You Need）。
- 如不存在，先下载到宿主，再通过前端或 API 上传至对应知识库。

## 测试用例设计
### 基础配置
- 嵌入模型默认值显示与选择：当为空时显示 `BAAI/bge-m3` 或系统默认；选择列表来自 `/api/embedding/models`。
- 恢复默认设置：`POST /api/kb/{name}/config/reset` 后再 `GET /api/kb/{name}/config` 值恢复。
- 保存配置：点击“保存配置”按钮触发 `POST /api/kb/{name}/config` 全量提交。

### 检索参数覆盖
- 覆盖项：`stack`、`vector_backend`、`collection_name`、`top_k_default`、`candidate_k`、`vector_weight`、`keyword_weight`、`reranker_filter_threshold`、`rrf_k`、`web_search_enabled`、`web_search_provider`、`grade_threshold`、`hallucination_threshold`。
- 预期：`/api/chat` 与 `/api/chat/stream` 内部 `retrieve/rerank/grade/hallucination` 阶段使用 KB 值。

### 向量后端选择
- 为 KB 分别设置 `milvus/qdrant/elasticsearch/local/auto`，执行 `/api/vector-store/search` 与 `/api/chat/stream`，观察集合与速度差异。
- 指定 `collection_name`，验证检索与索引使用该集合。

### 端到端摄取
- 上传 `kb_laws.pdf` 至 `kb_laws`，`kb_paper.pdf` 至 `kb_paper`。
- `GET /api/kb/{KB}/documents` 可见文档；检索测试返回相关块与引用。

### 嵌入诊断
- `POST /api/debug/embed` 返回 `dim/norm/sum/head`。
- `POST /api/debug/embed/kb` 返回 `model` 字段与向量统计，确认使用 KB 的嵌入模型。
- 日志不应出现 `POST https://dashscope.aliyuncs.com/api/v1/embeddings 404`，应使用服务端点或兼容模式端点。

### 前端操作
- 配置页项均有默认值或即时保存，底部“恢复默认设置”“保存配置”工作正常。
- 检索测试区能按 Top K 展示结果，分数随参数变化。

## 执行步骤
1. 启动容器：`docker compose up -d backend frontend`（按需加向量后端 profile）。
2. 创建知识库：`POST /api/kb/create` 为 `kb_laws`、`kb_paper`、`kb_test_api`。
3. 配置嵌入与检索参数：`POST /api/kb/{name}/config` 设置各项值。
4. 上传 PDF：`POST /api/documents/upload?kb_name={KB}` 上传测试文件。
5. 嵌入调试：`POST /api/debug/embed` 与 `POST /api/debug/embed/kb` 检查模型使用与向量统计。
6. 向量检索：`POST /api/vector-store/search` 验证集合推断与结果。
7. 聊天检索：`POST /api/chat`、`POST /api/chat/stream` 验证阶段事件、引用与指标。
8. 恢复默认：`POST /api/kb/{name}/config/reset`，再次验证配置与检索行为。

## 验收标准
- 所有 API 指向容器端口 `3503`，系统状态显示容器路径与服务。
- 知识库配置更新后，检索阶段参数与结果符合预期权重与阈值。
- 嵌入模型按 KB 生效，DashScope 使用有效端点且无 404。
- 向量后端与集合名正确覆盖，索引与检索一致。
- 前端配置页控件默认值显示正确，“恢复默认设置”“保存配置”生效。

## 报告与追踪
- 记录每次用例的请求、响应、耗时与指标到测试报告；失败项登记缺陷并关联配置快照。
- 收集后端日志关键事件：检索阶段 metrics、嵌入端点访问、索引写入后端选择。

## 回归与自动化
- 提供脚本化端到端测试（见 `scripts/qa/run_e2e.sh`），在 CI 或本地容器环境执行。
- 变更嵌入器、检索节点、后端工厂时触发该套回归。
