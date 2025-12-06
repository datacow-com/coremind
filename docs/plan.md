# 文档与图片 RAG 实施与 UI 可视化计划

## 目标
- 本地/私有云优先，处理文档（PDF/Office/HTML/Markdown）与图片（PNG/JPG），默认 Qdrant + Elasticsearch。
- 队列化 ingest，全阶段可视化（批次/文档级），策略可由 UI 选择（分块、embedding、重排、索引后端等）。
- 受控引用回答，支持页码与 bbox；UI 可管理索引与策略。

## 里程碑
1) ingest-pipeline  
   - 图片 OCR/VLM（版面/表格/图文抽取），统一 chunk schema（block_type/bbox/media_type）。  
   - OCR/VLM 选择策略（可在 UI 配置，支持多提供商回退）：  
     - 优先本地/私有化：DeepSeek OCR（成本低、中文友好）→ Qwen-VL（图文理解/表格/版面）→ 火山 OCR 视觉服务（高鲁棒、票据/卡证等场景）。  
     - 支持按场景路由：纯文本/票据优先 DeepSeek/火山 OCR；版面/表格/复杂图文优先 Qwen-VL；失败自动回退；记录 provider 与置信度入 metadata。  
     - 批量并发与速率限制：按 provider 配额配置 QPS 上限，超限自动切换/排队。
   - 队列化阶段：上传 → 抽取 → 分块 → embedding → 索引，失败重试 + 死信。  
   - 对象存储分桶：原件/转写/元数据/摘要；元数据入 PostgreSQL（批次/版本/质量/来源）。

2) storage-index  
   - 默认 Qdrant，ES 做关键词/过滤，保留 Milvus 兼容。  
   - 索引管理 UI：集合/KB 列表、chunk/文档计数、清理/重建入口；冷热分层（近期批次优先）。

3) retrieval-qa  
   - 混合检索 RRF + Cross-Encoder 重排；生成 JSON 引用含页码/bbox；无依据返回“未找到”；幻觉阈值可配。

4) quality-governance  
   - 去重/SimHash、语言检测、噪声/长度过滤，质量分入 metadata；敏感词/PII 过滤。  
   - OTel 埋点：阶段耗时/失败率/召回质量，仪表盘 + 告警。

5) UI 可视化与策略控制（中等粒度）  
   - 进度：批次/文档级阶段状态（排队/进行/成功/失败）、耗时、错误原因，实时刷新。  
   - 策略选择：上传/KB 设置中可选分块策略（长度/版面/表格优先）、embedding 模型、重排模型、索引后端（Qdrant/ES/Milvus）、top_k 等。  
   - 任务与重试：失败任务可在 UI 触发重试/跳过；展示死信队列摘要。  
   - Embedding 进度：显示已完成 chunk / 总 chunk、维度/模型名、预计剩余时间。  
   - Chunk/Embedding 精细化：按文件类型/大小使用不同分块与 embedding batch；UI 展示并可选预设。  
   - 索引管理：列出集合、文档/块数、占用量；支持删除文档、重建集合、查看最近索引批次。

6) deployment-ops  
   - docker-compose 扩展 backend/frontend/nginx + qdrant + elasticsearch + redis + minio，可选 milvus。  
   - 模型默认：DashScope(Qwen) LLM/Embedding + 本地 BGE reranker；图片 OCR + 可选 Qwen-VL。  
   - 提供 e2e 冒烟与批量导入脚本，覆盖 UI 触发与 API 路径。

## 关键文件参考
- 路由/管线：`server/routes.py`、`core/ingestion/*`、`core/nodes/*`、`core/graph.py`
- 存储/索引：`core/storage/*.py`、`core/storage/backend_registry.py`、`core/storage/index_router.py`
- 配置：`server/config.py`、`core/model_gateway/config_store.py`
- 部署：`docker-compose.yml`、`nginx.conf`
- 前端：`frontend/src/pages/*`、`frontend/src/lib/api.ts`、`frontend/src/hooks/useSse.ts`，新增任务/状态组件
- 脚本：`scripts/e2e_api_test.py`（可扩展批量导入用例）

## 交付物
- 更新的 compose/配置模板；文档+图片 ingest 节点与队列化路径及监控埋点。  
- UI：进度可视化、策略选择、重试入口、embedding 进度、索引管理视图。  
- 引用输出（页码/bbox）约定与前端对接说明。  
- e2e 测试脚本与批量导入示例。

## 架构设计（面向 100,000G 解析与端到端消费，按里程碑展开）

### 总体容量与分层
- 规模假设：100,000G ≈ 100TB 原始数据（文档+图片），平均 1MB/文档估算 1e8 文档上限；实际按批次导入（建议 1–5TB/批次）。
- 分层存储：  
  - 对象存储（MinIO/Ceph）：原件、转写 Markdown/JSON、派生摘要，分桶（raw/derived/meta）。  
  - 元数据（PostgreSQL）：文档/批次/版本/来源/质量分/阶段状态/错误；任务表与死信表。  
  - 向量（Qdrant）：主索引，按 KB/collection 分库，支持 shard+replication。  
  - 关键词/过滤（Elasticsearch）：BM25 + 结构过滤，分索引按 KB/批次；保留 Milvus 兼容路径。  
  - 缓存/队列（Redis Streams）：调度、心跳、速率控制；未来可替换 Kafka/RabbitMQ。
- 热/冷分层：近期批次为热（优先加载向量、开启压缩=false），旧批次冷（向量压缩/延迟加载、只保留 BM25 或粗向量）。UI 可切换批次热度。

### 1) ingest-pipeline（文档+图片）
- 组件角色：  
  - Ingest Orchestrator：监听上传事件→写对象存储→投递队列；记录任务/阶段表。  
  - Parser Workers：文档解析（版面/表格/标题）、图片 OCR/VLM；按 mime 路由。  
  - Chunker Workers：按策略（长度/版面/表格优先/图片块 bbox）切分，写 chunk+metadata。  
  - Embed Workers：批量 embedding（按类型/大小分批大小），写向量；失败重试 N 次后入死信。  
  - Indexer Workers：写 Qdrant+ES；更新任务状态。  
  - QC Workers：去重(MD5+SimHash)、语言检测、质量评分、敏感词/PII 过滤。
- 阶段定义（UI 可视化）：upload → parse → chunk → embed → index → finalize；每阶段记录开始/结束时间、进度(已完成/总)、错误。  
- 策略可选：分块长度/版面优先、图片 OCR/VLM 开关、embedding 模型、batch 大小、top_k、向量后端、关键词后端、是否跳过低质量块。  
- 弹性与吞吐：  
  - 并行度：按批次拆分子任务，队列分片；图片与文档可用独立 worker 组。  
  - I/O：对象存储写入使用多分片上传；解析/embedding 用本地 NVMe 缓存。  
  - 失败处理：幂等任务 ID；重试次数与冷却时间；死信 UI 可重放或跳过。

### 2) storage-index（Qdrant + ES）
- Qdrant：  
  - 集群 3+ 节点，副本数=2，分片按 KB/批次；启用压缩（旧批次可用 scalar/quantized）。  
  - Collection 命名：`kb_{name}_v{version}`；支持 per-KB 维度/后端配置。  
  - 写入路径：批量 upsert；错误重试；写后校验 count。  
- Elasticsearch：  
  - 3 data + 1 master (容错)，分索引 `kb_{name}_docs`；禁用安全或使用内网凭据。  
  - 字段：content, metadata(block_type/bbox/page/lang/quality/batch/version/source)。  
  - 刷新策略：bulk 导入时关闭自动刷新，阶段结束再 refresh。
- PostgreSQL：  
  - 表：documents、batches、tasks、task_errors、chunks_meta（轻量）、quality_scores；索引 batch_id/status；任务状态更新幂等。  
  - 支持软删除旧版本（标记+延迟清理向量/ES）。
- 热/冷策略：UI 可调批次热度，后台触发向量压缩/卸载、只保留 BM25。

### 3) retrieval-qa
- 流程：route → retrieve(RRF 向量 + BM25 + 结构过滤) → rerank(Cross-Encoder) → generate(JSON 引用) → hallucination(optional)。  
- 语义检索策略：  
  - 混合：向量（Qdrant）+ BM25（ES）+ 结构过滤（lang/quality/batch/media/block_type）。  
  - 向量配置：主集合使用 BAAI/bge-m3（中文/多语言），支持 per-KB embedding_model 覆盖；图片块可存两路向量（OCR 文本向量、VLM 标题/说明向量）。  
  - Query 预处理：语言检测→选择集合；可选 Query Rewriting（LLM 简化）与伪相关反馈（PRF）扩展关键词。  
  - 召回融合：RRF + 质量/媒体权重；可对表格/标题块加权；冷批次可降采样 top_k。  
- 重排：Cross-Encoder（BGE reranker），可选模型切换；过滤低于阈值。  
- 生成：JSON 引用含页码/bbox/doc_id/block_type；图片块可回传裁剪坐标；无依据返回“未找到”。  
- 缓存：热门 query 结果缓存（Redis）；embedding 结果本地 LRU。  
- SLA：检索 P95 < 1.5s（热批次），冷批次回退 BM25 或较低 top_k。

### 4) quality-governance
- 去重：文件 MD5 + 段级 SimHash；重复文档可跳过或合并版本。  
- 质量：噪声/长度阈值、OCR 置信度、版面完备度；质量分入 metadata，检索可过滤。  
- 合规：敏感词/PII 过滤链路放在 parse/qa 前；失败任务入死信并标注原因。  
- 观测：OTel 埋点 + Prometheus 指标；仪表盘覆盖阶段耗时/失败率/召回量、队列深度、向量/ES 写入耗时。

### 5) UI 可视化与策略控制（中等粒度）
- 进度看板：批次/文档视角，阶段状态、耗时、错误摘要、已完成 chunk / 总数、embedding 预计剩余时间。  
- 策略配置：上传/KB 设置页可选分块策略、embedding/重排模型、向量/关键词后端、top_k、batch 大小、质量过滤开关。  
- 任务操作：失败任务重试/跳过，死信重放；批次暂停/继续。  
- Chunk/Embedding 精细化：按文件大小/类型自动选预设（UI 可见、可覆盖）。  
- 索引管理：列出集合/KB、文档/块数、占用量、热度；支持删除文档、重建集合、查看最近批次。  
- 后端接口：  
  - GET/POST `/api/ingest/batches`（列表/创建/策略）、`/api/ingest/tasks`（状态/重试/跳过）、`/api/index/collections`（查看/重建/删除）、`/api/ingest/metrics`（阶段指标）。  
  - SSE/WSS 通知进度更新，前端 useSse 持续刷新。

### 6) deployment-ops
- Dev/单机：docker-compose（backend/frontend/nginx + qdrant + elasticsearch + redis + minio，可选 milvus）。  
- Prod/大规模：推荐 K8s，分离在线检索与批处理节点；对象存储用独立集群（Ceph/MinIO 多节点）；Qdrant/ES 集群独立部署。  
- 资源建议（起步）：  
  - Qdrant：3×(8C16G+NVMe)，副本 2；ES：3×(8C32G，30–50GB heap)。  
  - 解析/OCR/VLM：GPU 节点若需 VLM，纯 OCR 可 CPU+少量 GPU；embedding 节点可多卡批量。  
  - 带宽：内网 10–25GbE；对象存储与 Qdrant/ES 同机架优先。  
- CI/CD：lint+e2e（含批次导入脚本）、负载回归基准；配置模板与环境变量示例。

### 7) 生产级定义与策略（补充）
- 可用性与 SLO：  
  - 在线检索 API P95 < 1.5s（热批次），可用性 ≥ 99.9%；ingest 管道支持断点续传与幂等。  
  - 速率限制与配额：按租户/KB 配置 QPS、每日 tokens/调用数；触发告警与拒绝策略。  
- 稳定性：  
  - 关键路径设熔断/重试（OCR/VLM/LLM/向量库/ES）；队列堆积阈值告警；死信重放。  
  - 写入幂等：任务/批次 ID，索引 upsert；软删除版本化。  
- 安全与合规：  
  - 敏感词/PII 过滤（解析后、生成前）；最小权限访问存储与索引；审计日志。  
  - 数据分域：按 kb_name/collection 隔离；可选租户级密钥。  
- 监控与运维：  
  - 指标：阶段耗时/失败率、队列深度、OCR/VLM 成功率与耗时、向量/ES 写入耗时、检索延迟。  
  - 日志/追踪：OTel trace 覆盖 ingest/retrieval；集中日志（Loki/ELK）。  
  - 容量/成本：对象存储、Qdrant、ES 持续监控，冷热分层、压缩策略执行可观测。  
  - 灰度与回滚：索引版本化（新集合并行写，切换别名），模型/策略灰度发布。

