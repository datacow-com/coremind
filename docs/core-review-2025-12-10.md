# Core 目录复审报告（2025-12-10）

> **范围**：`/core` 全量代码（含子目录）  
> **基线文档**：`docs/tech/system-design.md` v2.0, `docs/tech/large-pdf-processing.md`, `docs/tech/implementation_plan.md`  
> **检查重点**：遗漏的算法；错误/静态/临时实现；缺失的核心业务逻辑  

---

## 1. 结论摘要

- **整体状态**：摄取/检索主链可跑，但存在路由缺口、多模态/视觉链条未闭环，若直接投产存在 P0/P1 风险。  
- **主要风险**：检索图缺条件映射（LangGraph 运行即报错）；GPU 解析仍有临时映射；多模态检索硬编码 channel；Router 未做扫描件判定；幻觉/语义缓存未接入图。  
- **建议顺序**：先修 P0（可用性/崩溃风险），再补 P1（设计对齐、质量闭环），最后优化 P2（性能与可观测性）。  

---

## 2. 高优先级问题（P0）

| 问题 | 影响 | 位置 |
|:-----|:-----|:-----|
| 检索图条件路由无映射，LangGraph 编译/运行时报错，意图路由失效 | 检索链直接异常，无法上线 | `core/graph.py`：`add_conditional_edges("router", intent_router)` 未提供映射，`rerank` 分支亦同 |
| 多模态检索硬编码 channel，跨租户隔离缺失 | 生产多租户数据泄露风险 | `core/retrieval/multimodal/retriever.py` `_search_text_vectors` 使用 `channel_id = "default"` |
| GPU 解析仍存在临时/占位映射 | OCR/VLM 可能走 YOLO 占位，版面/表格链路不可信 | `core/ingestion/nodes/parser/gpu_parser.py` 将 `paddle` 映射 `LocalYoloProvider`，且 DeepSeek/Qwen/Volc 未做版面/表格拆分与内容回填 |

---

## 3. 中优先级问题（P1）

| 问题 | 影响 | 位置 |
|:-----|:-----|:-----|
| Router 未做扫描件/版面判定，强制走 CPU 解析 | 扫描 PDF 走文本路径，OCR 漏召回 | `core/ingestion/nodes/router.py` |
| 摄取图缺质量控制/清洗/重试节点 | 质量不可控，错误无法内环重试 | `core/ingestion/graph.py` 仅 loader→router→parser→chunker→embedder→indexer |
| StrategyConfig 字段仍嵌套 `chunking`，与文档平铺配置不一致 | 前后端/节点读取易错 | `core/state.py` |
| 多模态检索集合存在性已实现，但索引/检索语义未对齐 | 图像/表格检索依赖 channel/default、不使用 state channel_id | `core/retrieval/multimodal/retriever.py` |
| 幻觉检测、语义缓存未纳入检索图 | 质量与成本控制缺失 | `core/graph.py`（无语义缓存节点；HallucinationChecker 需连接引用核查阈值） |
| RAPTOR/GraphRAG 扫描全量，缺分页与 channel/kb 过滤 | 大库易 OOM，跨租户泄露 | `core/algorithms/raptor_deep.py`, `graphrag_deep.py` 使用 `list_all_meta()` 无过滤 |

---

## 4. 低优先级问题（P2）

| 问题 | 影响 | 位置 |
|:-----|:-----|:-----|
| 视觉链缺阅读顺序/表格结构回写到块 | 召回权重与引用定位受限 | `core/vision/layout_analyzer.py` 与 chunker 集成松散 |
| 多模态检索未做跨模态融合权重自适应 | 不同模态排序可调性不足 | `core/retrieval/multimodal/retriever.py` |
| 观察性缺口：节点级 OTel 埋点覆盖有限 | 排障与性能分析困难 | 多数节点未设置 span 属性 |

---

## 5. 目录级评审

### 5.1 graph（检索图）
- **问题**：条件路由未传映射；无语义缓存节点；HallucinationChecker 仅追加警告，无引用核查结果参与决策。  
- **建议**：`add_conditional_edges` 补映射；引入语义缓存节点；幻觉检测输出用于调低置信度/触发降级。  

### 5.2 ingestion（摄取）
- **Router**：无扫描判定，强制 CPU 路径。  
- **Graph**：缺 QC/Cleaner/Error-retry/Finalizer，无法质量兜底。  
- **GPU Parser**：`paddle`→YOLO 临时映射，未做表格/图像分支与 OCR 回填。  
- **Chunker**：已补 semantic/heading_based/元数据加权（👍）。  
- **Loader**：已支持大文件 lazy/下载，但 Parser 端未见分页消费衔接。  

### 5.3 retrieval
- **HybridRetriever**：`kb_cfg` 问题已修复（👍）。  
- **MultimodalRetriever**：channel 硬编码 default，未用 state.channel_id；跨模态权重固定。  
- **Graph**：无语义缓存，幻觉检测未影响路由。  

### 5.4 storage
- **vector_store**：已补 `collection_exists`（👍）。  
- **index_router**：大规模/多租户过滤需二次确认，RAPTOR/GraphRAG 仍全量扫描。  

### 5.5 algorithms
- 核心算法在位，但调用侧缺分页/过滤；Louvain/摘要存在，需接入 channel/kb 过滤与限流。  

---

## 6. 修复建议与优先级

### P0（立即修复）
1. **检索图路由映射**：为 `router`/`rerank` `add_conditional_edges` 提供映射，确保 LangGraph 可编译运行。  
2. **多模态检索的 channel 隔离**：使用 `state.channel_id` 生成 collection/index，移除硬编码 `"default"`。  
3. **GPU 解析 provider 路由**：恢复 `paddle`→真实 OCR（或直连 paddleocr），保留 YOLO 仅用于检测；对 DeepSeek/Qwen/Volc 结果写入表格/图片/文本分块。  

### P1（设计对齐）
1. **Router 扫描判定**：轻量检测扫描件/图片 PDF，路由 GPU OCR。  
2. **摄取图质量闭环**：增加 QC/Cleaner/Retry/Finalizer/SSE 进度。  
3. **StrategyConfig 平铺字段**：对齐文档/UI（`chunking_mode` 等），兼容旧字段。  
4. **语义缓存/幻觉检测接入图**：在图中串联，幻觉结果影响置信度/降级。  
5. **RAPTOR/GraphRAG**：`list_all_meta` 增加 channel/kb 过滤与分页，避免全表扫描。  

### P2（增强与可观测）
1. **视觉信息回写**：LayoutAnalyzer/表格结构写入 parsed_blocks，供 chunker 与权重使用。  
2. **跨模态自适应权重**：配置化 vector/keyword/image/table 权重与阈值。  
3. **OTel 埋点覆盖**：为关键节点添加 span 属性（文件/页数/耗时/错误）。  

---

## 7. 验证建议
- **单测**：router 路由分支、graph 编译、chunker 语义/标题模式、多模态检索 channel 隔离。  
- **集成**：大文件 PDF (150MB) 摄取 → GPU OCR → 分块 → 索引；表格/图像检索返回多模态结果；幻觉检测启用时触发告警降级。  
- **性能/可靠性**：并发检索压测，验证路由/缓存/熔断；大文件流式内存占用监控。  

---

## 8. 函数级问题与证据

1) **检索图条件路由缺映射，LangGraph 运行时报错**  
```289:298:core/graph.py
    def intent_router(state: RetrievalState) -> str:
        ...
    graph.add_conditional_edges("router", intent_router)
```
`add_conditional_edges` 未提供路由表，编译/运行会报参数错误，意图路由失效。

2) **多模态检索硬编码 channel，缺租户隔离**  
```227:236:core/retrieval/multimodal/retriever.py
            # Get collection name
            channel_id = "default"  # TODO: Get from context
            collection = channel_collection_name(channel_id, kb_name)
```
channel_id 强制 "default"，跨租户数据无法隔离。

3) **摄取路由未做扫描判定，扫描 PDF 走 CPU 文本路径**  
```11:24:core/ingestion/nodes/router.py
    if cfg.get('force_ocr', False):
        return "gpu_parser"
    ...
    if state['file_type'] == 'pdf':
        # For MVP, assume CPU unless forced.
        return "cpu_parser"
```
缺少扫描件检测/版面判定，扫描 PDF 会跳过 OCR。

4) **GPU 解析仍有临时/占位映射，未做 OCR 回填**  
```306:314:core/ingestion/nodes/parser/gpu_parser.py
        self.providers = {
            "mock": MockOCRProvider(),
            "deepseek": DeepSeekOCR(),
            "qwen-vl": QwenVLProvider(),
            "volc_engine": VolcEngineOCR(),
            "paddle": LocalYoloProvider()  # Mapping paddle to local yolo pipeline for now
        }
```
`paddle` 被映射到 YOLO，YOLO 仅输出 bbox/unknown，无 OCR 文本回填，多模态/表格链路不可信。

5) **摄取图缺 QC/重试/Finalizer，异常无法内环处理**  
```13:44:core/ingestion/graph.py
    workflow.add_node("loader", LoaderNode())
    ...
    workflow.add_edge("embedder", "indexer")
    workflow.add_edge("indexer", END)
```
链路仅 loader→router→parser→chunker→embedder→indexer，缺质量校验、清洗、错误重试与最终状态节点。

6) **多模态检索未验证集合存在性时使用 channel default，可能返回空结果且无隔离**  
```205:213:core/retrieval/multimodal/retriever.py
        if self.enable_image_search:
            image_results = await self._search_image_vectors(kb_name, query_embedding)
            results.extend(image_results)
```
`_search_image_vectors` 内部亦未使用 state.channel_id；依赖前述硬编码导致多模态路径不可用或越权。

7) **幻觉检测结果未参与路由/置信度决策**  
```190:214:core/graph.py
    async def __call__(self, state: RetrievalState) -> RetrievalState:
        ...
        if result.get("score", 0) > cfg.get("hallucination_threshold", 0.5):
            state["final_answer"] = f"⚠️ 警告：回答可能包含不确定信息\n\n{answer}"
```
仅追加警告，不调整置信度/不触发降级或重试，质量控制缺闭环。

