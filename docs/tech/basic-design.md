这是一个基于 LangGraph 框架的深度详细设计文档。LangGraph 的有状态（Stateful）、循环（Cyclic）和多Actor特性，非常适合处理复杂的 RAG 流水线，特别是当我们需要在工作流中动态调整策略、处理失败重试以及进行多模态路由时。

本设计将之前的架构落地为具体的 LangGraph Node（节点）、Edge（边） 和 State（状态） 定义。

基于 LangGraph 的高性能 RAG 系统详细设计 (v4.0)
1. 核心设计理念

State as Config (状态即配置): 所有的策略参数（如 Chunk Size、OCR 引擎选择、Top-K）都存储在 LangGraph 的 State 中，由 UI 在启动图运行时注入。

Conditional Routing (条件路由): 利用 LangGraph 的 add_conditional_edges 实现 CPU/GPU 路径分流、失败重试及质量回退。

Human-in-the-loop (可选): 利用 LangGraph 的 Checkpointer，允许在“解析失败”或“低置信度”时暂停图运行，等待人工介入（UI 修复）后继续。

2. Ingestion Graph (数据摄取图)

这是处理 100TB 数据的核心流水线。我们将定义一个名为 IngestGraph 的状态图。

2.1 State Schema (状态定义)
code
Python
download
content_copy
expand_less
from typing import TypedDict, List, Optional, Dict, Any, Union
import operator

class IngestState(TypedDict):
    # --- 基础元数据 ---
    task_id: str
    file_path: str
    file_type: str  # 'pdf', 'image', 'docx', 'zip'
    batch_id: str
    
    # --- 策略配置 (来自 UI) ---
    # 示例: {"ocr_provider": "volc", "chunk_strategy": "semantic", "clean_model": "deepseek-v3"}
    strategy_config: Dict[str, Any]
    
    # --- 流水线数据 ---
    raw_text: Optional[str]
    images: List[Dict]      # [{"path": "...", "bbox": [...]}]
    parsed_blocks: List[Dict] # Markdown 结构块
    chunks: List[Dict]      # 最终切片
    vectors: List[List[float]]
    
    # --- 状态控制 ---
    retry_count: int        # 当前节点重试次数
    error_log: List[str]
    processing_stage: str   # 用于 UI 进度条: 'parsing', 'embedding', 'indexing'
2.2 Nodes (节点实现细节)
Node A: LoaderNode (加载与流式解压)

功能: 处理 IO 风暴。

策略实现:

检查 file_type。

若是 .zip/.tar 且 strategy_config['stream_unzip'] 为 True，则使用 Python generator yield 文件流，触发子图 (Subgraph) 运行（每个子文件一个新图）。

若是超大 PDF (>100MB)，仅加载 XRef 表，更新 State 标记为 lazy_load。

Node B: RouterNode (智能分流器)

逻辑: 这是 LangGraph 的 conditional_edge 核心决策点。

代码逻辑:

code
Python
download
content_copy
expand_less
def route_file(state: IngestState):
    cfg = state['strategy_config']
    # 强制 OCR 策略
    if cfg.get('force_ocr', False):
        return "gpu_vision_parser"
    
    # 自动探测
    if state['file_type'] in ['jpg', 'png']:
        return "gpu_vision_parser"
    elif is_scanned_pdf(state['file_path']):
        return "gpu_vision_parser"
    else:
        return "cpu_text_parser"
Node C1: CpuTextParser (低成本解析)

工具: PyMuPDF / Unstructured.

输出: 提取纯文本和基础表格结构，更新 state['parsed_blocks']。

Node C2: GpuVisionParser (多模态解析)

策略多样性:

读取 state['strategy_config']['ocr_provider']。

Case 'volc' (火山): 调用火山引擎 API，解析票据/复杂表格。

Case 'qwen' (通义): 调用 Qwen-VL-Max 进行通用图文理解。

Case 'local' (DeepSeek-Janus): 本地 GPU 推理。

异常处理: 若 API 调用超时，抛出异常，触发图的 Retry 机制。

Node D: SemanticCleaner (清洗)

模型: DeepSeek-V3。

逻辑: 仅当 strategy_config['enable_cleaning'] 为 True 时执行。

操作: 接收 parsed_blocks，修复 Markdown 语法，去除乱码，标准化表头。

Node E: ChunkerNode (动态分块)

策略:

Fixed: RecursiveCharacterTextSplitter (LangChain 原生)。

Semantic: 基于 NLP 边界或 Markdown Header (#, ##) 切分。

Proposition: 调用小模型将长句拆解为命题（Proposition）。

关键动作: 为每个 Chunk 生成 UUID，保留 bbox 和 page_num 到 metadata。

Node F: EmbedderNode (向量化)

工具: BGE-M3 (via Infinity Server)。

优化: 并不单条调用。此节点内部维护一个微批次（Mini-batch），累积到 64 条或 128 条再请求 Embedding 服务。

Node G: IndexerNode (入库)

目标: Qdrant + Elasticsearch。

策略:

Qdrant: 写入 Vector + Payload。若配置了 quantization: binary，则确认 Collection 配置是否匹配。

ES: 写入 Fulltext + Metadata。

终态: 更新 processing_stage 为 'completed'。

2.3 Graph Topology (图拓扑)
code
Python
download
content_copy
expand_less
from langgraph.graph import StateGraph, END

workflow = StateGraph(IngestState)

# 添加节点
workflow.add_node("loader", loader_node)
workflow.add_node("cpu_parser", cpu_text_parser)
workflow.add_node("gpu_parser", gpu_vision_parser)
workflow.add_node("cleaner", semantic_cleaner)
workflow.add_node("chunker", chunker_node)
workflow.add_node("embedder", embedder_node)
workflow.add_node("indexer", indexer_node)
workflow.add_node("retry_handler", retry_handler_node)

# 设置入口
workflow.set_entry_point("loader")

# 路由逻辑
workflow.add_conditional_edges(
    "loader",
    route_file,
    {
        "cpu_text_parser": "cpu_parser",
        "gpu_vision_parser": "gpu_parser"
    }
)

# 解析后的汇聚
workflow.add_edge("cpu_parser", "cleaner")
workflow.add_edge("gpu_parser", "cleaner")

# 后续流程
workflow.add_edge("cleaner", "chunker")
workflow.add_edge("chunker", "embedder")
workflow.add_edge("embedder", "indexer")
workflow.add_edge("indexer", END)

# 错误处理 (全局或节点级) - 简化示意
# 实际实现中使用 checkpointer 或专门的 error edge
workflow.compile()
3. Retrieval QA Graph (检索问答图)

检索端更强调推理（Reasoning）和循环优化（Looping）。

3.1 State Schema
code
Python
download
content_copy
expand_less
class RetrievalState(TypedDict):
    input_query: str
    chat_history: List[Dict]
    strategy_config: Dict[str, Any] # TopK, Temperature, RerankModel
    
    # 中间态
    rewritten_queries: List[str]
    retrieved_docs: List[Dict] # [Doc1, Doc2...]
    reranked_docs: List[Dict]  # [Doc1, Doc3...] (Sorted)
    is_relevant: bool          # Grader 结果
    
    # 最终结果
    final_answer: str
    citations: List[Dict]
3.2 Nodes (节点实现)
Node 1: QueryPreProcessor (预处理)

模型: DeepSeek-Lite / Qwen-Turbo.

功能:

Decomposition: 拆解复杂问题。

Rewrite: 补全指代（"它" -> "DeepSeek"）。

Intent: 判断是否查图表。若查图表，增加 image 类型的过滤条件。

Node 2: HybridRetriever (混合检索)

策略:

并发执行 Qdrant (Dense) 和 ES (Sparse/Keyword) 查询。

应用 RRF 融合算法。

Semantic Cache: 先查 Redis 缓存，命中则直接跳到 END。

Node 3: Reranker (重排)

模型: BGE-Reranker-v2-m3。

逻辑:

Input: Query + Top 50 Docs.

Output: Top 10 Docs with scores.

截断: 丢弃 Score < strategy_config['score_threshold'] 的文档。

Node 4: RelevanceGrader (相关性打分 - Optional)

模型: 小参数 LLM。

逻辑: 快速判断 Retrieve 到的 Top 3 文档是否真的能回答 Query。

Conditional Edge:

如果相关 -> Go to Generator.

如果不相关 -> Go to QueryPreProcessor (触发 Rewrite，最多重试 2 次)。

Node 5: CitationGenerator (生成)

模型: DeepSeek-V3 (Temperature = 0.1).

System Prompt:

"你是一个严谨的助手。必须基于提供的上下文回答。每句话末尾必须标注引用来源，格式为 <cite id='doc_id' bbox='...'>。</cite>"

3.3 Graph Topology
code
Python
download
content_copy
expand_less
qa_workflow = StateGraph(RetrievalState)

qa_workflow.add_node("preprocess", query_pre_processor)
qa_workflow.add_node("search", hybrid_retriever)
qa_workflow.add_node("rerank", reranker)
qa_workflow.add_node("grade", relevance_grader)
qa_workflow.add_node("generate", citation_generator)

qa_workflow.set_entry_point("preprocess")
qa_workflow.add_edge("preprocess", "search")
qa_workflow.add_edge("search", "rerank")
qa_workflow.add_edge("rerank", "grade")

def check_relevance(state):
    if state['is_relevant']:
        return "generate"
    else:
        # 防止死循环，检查 loop count
        return "preprocess" if state['loop_count'] < 2 else "generate"

qa_workflow.add_conditional_edges("grade", check_relevance)
qa_workflow.add_edge("generate", END)
4. UI 与 LangGraph 的策略对接 (The Bridge)

如何在 UI 上实现“可视化配置”并传导到这些 Node？

4.1 策略对象结构 (JSON)

前端配置页面生成的 JSON 对象，作为 input 传给 Graph。

code
JSON
download
content_copy
expand_less
{
  "batch_id": "batch_20241206_001",
  "strategy_config": {
    "ingestion": {
      "ocr_provider": "volc_engine_finance", // 场景化选择
      "ocr_concurrency": 5,
      "chunking": {
        "mode": "semantic",
        "max_tokens": 512,
        "overlap": 64
      },
      "embedding": {
        "model": "bge-m3",
        "batch_size": 64
      },
      "indexing": {
        "target": ["qdrant", "elasticsearch"],
        "quantization": "binary" // 100TB 关键策略
      }
    },
    "retrieval": {
      "rerank_model": "bge-reranker-v2-m3",
      "top_k": 10,
      "strict_mode": true // 开启后，无引用则不回答
    }
  }
}
4.2 前端实时可视化 (SSE)

LangGraph 支持 astream_events API。后端通过 Server-Sent Events (SSE) 将 Node 的状态变更推送到前端。

后端 (FastAPI + LangGraph):

code
Python
download
content_copy
expand_less
@app.post("/ingest/run")
async def run_ingest(request: IngestRequest):
    # 初始化状态
    initial_state = IngestState(
        file_path=request.path, 
        strategy_config=request.config
    )
    
    # 编译图并运行
    app = workflow.compile()
    
    async def event_generator():
        async for event in app.astream_events(initial_state, version="v1"):
            # 将 LangGraph 事件转换为前端进度数据
            if event["event"] == "on_chain_end":
                yield f"data: {json.dumps({'node': event['name'], 'status': 'done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

前端展示:

收到 on_node_start: gpu_parser -> UI 对应的 "OCR 处理" 节点亮起并显示 "Running..."。

收到 on_node_end: gpu_parser -> 节点变绿，显示耗时 "1.2s"。

5. 关键兼容性与多样性设计总结
5.1 兼容性 (Compatibility)

多模型兼容: Node 内部使用 Factory Pattern (工厂模式)。GpuVisionParser 根据 config 实例化 VolcParser 或 QwenParser 或 DeepSeekParser。

多向量库兼容: IndexerNode 同时适配 Qdrant Client 和 ES Client。若未来增加 Milvus，只需增加适配器，不改动图结构。

多文件类型兼容: LoaderNode 统一了流式 Zip 和 lazy PDF 的接口，下游节点只感知 Raw Data。

5.2 策略多样性 (Diversity)

成本 vs 质量: 用户在 UI 拉动滑块（"Speed" vs "Quality"），后端 State 自动调整 OCR 引擎（Paddle vs Volc）和 Rerank 阈值。

容错策略: 在 retry_handler 中定义策略，例如：OCR 失败自动降级为纯文本提取，或者 Embedding 失败进入死信队列供人工重试。

5.3 100TB 规模适配

Batch Processing: EmbedderNode 不是来一个处理一个，而是积攒 state 或使用 map 操作并行处理 chunks。

Async IO: 整个 LangGraph 基于 asyncio 运行，等待 GPU 推理时释放 CPU 资源处理 IO。

Checkpointer: 使用 Postgres 记录 Graph 状态。如果处理 100GB 文件中途服务器重启，重启后可直接从 Chunker 节点 Resume，无需重新 OCR。

这个基于 LangGraph 的设计实现了架构的可编程性和可视化，完美契合生产级高性能 RAG 的需求。