这是一个作为资深产品经理 (Senior PM) 为你定制的企业级 RAG 系统（代号：CoreMind） 产品需求文档 (PRD)。

本设计完全基于**“市场痛点导向”，融合了 RAGFlow 的深度解析能力、Dify 的灵活编排能力以及 MaxKB 的开箱即用体验。它不是简单的拼接，而是基于 LangGraph 架构的有机整合，旨在构建一个全生态、可进化**的智能知识中台。

产品需求文档 (PRD): CoreMind RAG - 下一代智能知识中台
文档属性 详情
产品代号 CoreMind (核心智脑)
版本号 V1.0 (MVP) -> V2.0 (Platform)
文档状态 Final / Execution Ready
主要贡献者 Product Lead, System Architect
核心依赖 LangGraph (编排), Gemini 3 (推理/视觉), Milvus (存储)

1. 市场洞察与用户心声 (Market & User Voice)

在设计功能之前，我们必须直面当前 RAG 市场的真实痛点。这是我们“极高价值”的来源。

1.1 用户真实心声 (Voice of Customer)

企业知识库管理员：“我上传了原本精美的 PDF 财报，结果系统读出来的全是乱码，表格里的数据错位，检索出来的答案根本不敢用。（痛点：解析不可用）”

业务人员：“它只能回答文档里的话。如果问最近的新闻或者文档里没有的常识，它就开始胡说八道（幻觉）。（痛点：知识封闭，无联网）”

开发者：“Dify 很好，但对于我们这种只想快速把知识库嵌入官网的公司来说，配置还是太重了。MaxKB 很简单，但流程又太死板，没法加自定义逻辑。（痛点：灵活性与易用性的矛盾）”

CTO：“我不仅要一个聊天机器人，我要的是一个能生成 API 的知识中台，支撑我所有的内部业务系统。（痛点：生态隔离）”

1.2 核心价值主张 (Value Proposition)

所见即所得的解析 (WYSIWYG Ingestion)：像人类阅读一样“看”文档（视觉解析），而非代码式提取。

图导向的智能编排 (Graph-Native)：基于 LangGraph 的“检索-反思-修正”闭环，拒绝线性傻瓜式问答。

无缝生态集成 (API First)：从第一天起就是 Headless 架构，UI 只是能力的展示窗口。

2. 产品总体架构 (High-Level Architecture)

采用 ACIS (Acquisition - Cognition - Interaction - Service) 四层架构。

L1 数据获取层 (Acquisition): Visual Parser Engine (核心差异化，对标 RAGFlow)。

L2 认知与编排层 (Cognition): LangGraph Orchestrator (核心大脑，对标 Dify)。

L3 交互与服务层 (Interaction): Chat UI + Management Console (对标 MaxKB)。

L4 生态接口层 (Service): OpenAPI Gateway + Plugin System。

3. 详细功能需求 (Functional Requirements)
   3.1 核心模块一：视觉驱动的数据解析 (Visual Ingestion Engine)

优先级：P0 | 核心对标：RAGFlow

解决“Garbage In”问题的终极方案。

3.1.1 多模态文件支持

支持格式：PDF, DOCX, PPTX, EXCEL, Images, Markdown, HTML, EML。

深度视觉解析 (Deep Vision Parsing)：

逻辑：对于 PDF/PPT，先渲染为高分辨率图片。

版面分析：使用轻量级检测模型（YOLO/LayoutLM）识别 Header, Footer, Sidebar, Table, Figure。

智能去噪：自动剔除页眉、页脚、页码，避免干扰检索。

3.1.2 智能表格还原 (Table Recovery)

功能：识别文档中的表格区域，进行图像裁切。

VLM 转录：调用 Gemini 3 Vision，提示词：“将此表格图片转换为 Markdown 格式，保持数值精确，保留合并单元格结构”。

价值：确保财报、技术手册中的参数检索准确率达到 95% 以上。

3.1.3 图片理解 (Figure Understanding)

功能：检测文档中的插图、流程图。

Captioning：生成详细的图片的文字描述（Alt Text），并建立索引。

3.1.4 动态分块策略 (Dynamic Chunking)

提供“语义分块”、“固定字符分块”、“父子索引（Parent-Child Indexing）”三种策略。

3.2 核心模块二：自适应混合检索 (Adaptive Retrieval)

优先级：P0 | 核心对标：Enterprise Search

解决“找不到”和“查不准”的问题。

3.2.1 混合检索 (Hybrid Search)

Vector Search: 语义召回（Milvus/PgVector）。

Keyword Search: 关键词/术语召回（BM25）。

加权融合: 支持动态配置两者权重（例如：技术文档关键词权重 0.7，语义权重 0.3）。

3.2.2 多级重排序 (Multi-stage Reranking)

集成 BGE-Reranker-v2 或 Cohere Rerank。

逻辑：召回 Top-100 -> Rerank -> 截取 Top-10 给大模型。

3.2.3 引用溯源 (Traceability)

原文高亮：生成的答案必须带有 [1] 引用标记。点击标记，在右侧 PDF 预览窗口精准高亮对应的切片位置（利用解析时记录的 bbox 坐标）。

3.3 核心模块三：Graph 智能编排 (Graph Orchestration)

优先级：P1 | 核心对标：Dify / LangGraph

解决“逻辑简单”和“任务无法执行”的问题。

3.3.1 意图识别路由 (Intent Router)

系统自动判断用户 Query 类型：

Fact QA: 直查知识库。

Summary: 总结全文。

Web Info: 触发联网搜索。

Instruction: 执行特定动作。

3.3.2 自我修正流程 (Self-Correction Loop)

Grade Documents: 检索后，LLM 快速打分“文档是否相关”。

Fallback: 如果无相关文档，自动跳转到 Web Search 节点。

Hallucination Check: 生成答案后，再次校验“答案是否由文档支持”。

3.3.3 联网搜索增强 (Web Search)

集成 Tavily / Serper / DuckDuckGo。

支持将搜索结果 URL 内容抓取并临时作为上下文注入。

3.4 核心模块四：系统管理与 API 生态

优先级：P1 | 核心对标：MaxKB

3.4.1 模型中立网关 (Model Gateway)

支持 OpenAI, Anthropic, Gemini, DeepSeek, Ollama (Local)。

支持为不同任务（解析、检索、对话）分配不同的模型。

3.4.2 极简嵌入 (Embed-Anything)

提供 JS SDK，一行代码将 Chatbot 嵌入第三方网页。

提供类似 MaxKB 的“发布为应用”功能，生成独立 URL。

3.4.3 运营分析 (Analytics)

Token 消耗统计。

用户提问热词分析。

点踩优化：用户“点踩”的记录，自动加入“负样本池”，用于优化下一次检索。

4. 非功能性需求 (NFR) - 高性能与安全
   4.1 性能指标 (Performance)

解析延迟：PDF 解析速度 < 3秒/页（开启 GPU 加速）。

首字延迟 (TTFT)：流式输出 < 1秒。

并发能力：单节点支持 50 QPS，支持 K8s 水平扩展。

4.2 数据安全 (Security)

PII 过滤：在送往 LLM 前，通过 Presidio 或正则自动掩盖身份证、手机号等敏感信息。

沙箱环境：代码执行（如 Python解释器）必须在 Docker 隔离容器中运行。

RBAC：基于角色的权限控制（Dataset 级权限）。

5. 开发路线图与阶段规划 (Roadmap)

我们不追求一步到位，而是采用 MVP + 迭代 模式。

Phase 1: The Core Engine (MVP) - "能读懂，能回答"

目标：完成基于 Gemini 3 Vision 的 PDF 解析 + 基础 RAG 问答。

关键交付：

Visual Parser (PDF -> Markdown).

Milvus 集成 + 混合检索。

基于 LangGraph 的线性流程 (Retrieve -> Generate)。

简单的 Stream Chat UI。

Phase 2: The Adaptive Brain - "能思考，能联网"

目标：引入 Router 和 Web Search，减少幻觉。

关键交付：

Intent Router 节点。

Web Search Tool 集成。

Self-Correction (Grade Documents) 节点。

后台管理界面（知识库管理、Prompt 编排）。

Phase 3: The Ecosystem - "全平台，API化"

目标：对外开放能力，支持复杂工作流。

关键交付：

OpenAPI 完整文档。

JS 嵌入组件。

多租户权限系统。

运营数据看板。

6. 对 Vibe Coding 的特别指导 (Implementation Notes)

为了让 Gemini 3 协助你快速完成此 PRD 的代码落地，请注意以下设计细节：

LangGraph State 设计：

必须在 State 中包含 web_search_needed: bool 和 hallucination_score: float 字段，这是实现“智能”的关键。

视觉模型的 Token 消耗：

Gemini 3 的 Vision 能力虽然强，但 Token 消耗大。设计代码时，增加一个 ParsingRule 开关：默认用 OCR，只有检测到复杂版面时才自动升级调用 Vision Model。

前端交互：

不要只做 Chat。要在左侧做 Chat，右侧做 PDF Preview。当 AI 说“参考自第 3 页”时，右侧 PDF 自动滚动到第 3 页并画框。这才是“极高价值”的体验。

此 PRD 融合了 RAGFlow 的深（解析精度）、Dify 的广（编排能力） 和 MaxKB 的快（部署体验），并依托 LangGraph 保证了架构的先进性和未来的可扩展性。这是一个具备极强市场竞争力的产品设计。
