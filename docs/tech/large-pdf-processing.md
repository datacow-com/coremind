# 大规模多模态数据处理方案

> **场景**: 100~500TB 多模态数据资产
> **数据类型**: PDF、视频、图像、Office (Excel/Word/PPT)
> **作者**: 算法工程师
> **版本**: v1.1
> **日期**: 2025-12-08

---

## 0. 与能力框架的关系

本方案中的处理能力需与 `core/capabilities` 框架对接，确保：

| 原则 | 本方案落地 |
|:-----|:----------|
| **可见性** | 每种处理能力对应 UI 能力卡片 |
| **可配置** | KB 配置中选择启用哪些处理器 |
| **场景化** | 按数据类型自动匹配处理链 |
| **即用性** | 处理器懒加载，配置热更新 |
| **显化** | 处理进度、质量分数实时反馈 |

**能力映射**:
- PDF 版面分析 → `enhanced.table_recognition`, `enhanced.ocr`
- 视频处理 → `pro.video_understanding`
- 图像理解 → `enhanced.image_understanding`
- Excel/Office → `pro.excel_analysis`, `basic.text_extraction`
- 漫画识别 → `pro.comic_recognition`

---

## 1. 挑战分析

### 1.1 规模挑战

| 指标 | 量级 | 影响 |
|:-----|:-----|:-----|
| 总数据量 | 100~500 TB | 存储成本高，I/O 瓶颈 |
| 单文件大小 | >100 MB | 内存压力，无法全量加载 |
| 估算文件数 | 100万~500万 | 任务调度复杂 |
| 页面数 | 数十亿 | 索引/检索压力 |

### 1.2 内容挑战

| 内容类型 | 难点 | 解决方向 |
|:---------|:-----|:---------|
| **表格** | 复杂布局、跨页表格 | 专用表格检测模型 |
| **图像/漫画** | 语义理解、OCR | VLM + 区域 OCR |
| **扫描件** | 低质量、倾斜 | 预处理 + 增强 |
| **混合布局** | 多列、浮动元素 | Layout Analysis |

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       任务调度层 (Task Orchestration)             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Ray Cluster │  │ Celery      │  │ Kubernetes Jobs         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────┐
│                       处理管道层 (Processing Pipeline)           │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ 预处理   │──▶│ 版面分析 │──▶│ 内容提取 │──▶│ 后处理/索引  │ │
│  │ Stage-1  │   │ Stage-2  │   │ Stage-3  │   │ Stage-4      │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘ │
│       │              │              │               │           │
│       ▼              ▼              ▼               ▼           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │               GPU Worker Pool (弹性伸缩)                     ││
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   ││
│  │  │GPU-1│ │GPU-2│ │GPU-3│ │GPU-4│ │GPU-5│ │GPU-6│ │GPU-N│   ││
│  │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────────────┬──────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────┐
│                       存储层 (Storage)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ 阿里云 OSS  │  │ Qdrant 集群 │  │ Elasticsearch 集群      │  │
│  │ (原始文件)  │  │ (向量索引)  │  │ (全文检索)              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 处理管道详解

```
PDF 输入
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage-1: 预处理 (CPU 密集)                                       │
├─────────────────────────────────────────────────────────────────┤
│ • 文件校验 (损坏检测、格式识别)                                   │
│ • 元数据提取 (标题、作者、页数)                                   │
│ • 分页处理 (大文件拆分为页面任务)                                 │
│ • 扫描件检测 (判断是否需要 OCR)                                   │
│ • 图像预处理 (去噪、纠偏、二值化)                                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage-2: 版面分析 (GPU 密集)                                      │
├─────────────────────────────────────────────────────────────────┤
│ • 页面转图像 (PDF → PNG, 300 DPI)                                │
│ • 区域检测 (YOLO/LayoutLMv3)                                     │
│   - text_block, table, figure, chart, equation, header, footer  │
│ • 阅读顺序排序 (XY-Cut / Reading Order)                          │
│ • 表格结构识别 (行/列检测)                                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage-3: 内容提取 (GPU 密集, 可并行)                              │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │
│ │ 文本 OCR    │  │ 表格识别    │  │ 图像/漫画理解           │   │
│ │             │  │             │  │                         │   │
│ │ • PPOCRv4   │  │ • TableTransformer │ • Qwen-VL / GPT-4V  │   │
│ │ • Paddle    │  │ • TableNet  │  │ • DeepSeek-VL           │   │
│ │ • EasyOCR   │  │ • CascadeTabNet │ • 多模态 Embedding     │   │
│ └─────────────┘  └─────────────┘  └─────────────────────────┘   │
│         │                │                     │                │
│         └────────────────┼─────────────────────┘                │
│                          ▼                                      │
│                  结构化 Markdown 输出                            │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage-4: 后处理与索引                                            │
├─────────────────────────────────────────────────────────────────┤
│ • 语义分块 (Semantic Chunking)                                   │
│ • 表格 → CSV/Markdown 转换                                       │
│ • 向量嵌入 (BGE-M3 / text-embedding-3)                           │
│ • 双路索引 (Qdrant + Elasticsearch)                              │
│ • 质量评分 (OCR 置信度、完整性)                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块设计

### 3.1 大文件流式处理

```python
class StreamingPDFProcessor:
    """
    流式 PDF 处理器，支持超大文件分页处理
    """

    CHUNK_SIZE = 10  # 每批处理 10 页

    async def process(self, pdf_path: str, channel_id: str) -> AsyncIterator[PageResult]:
        """
        流式处理 PDF，逐页/批次返回结果

        1. 不一次性加载整个 PDF 到内存
        2. 按批次处理并 yield 结果
        3. 支持断点续传
        """
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        total_pages = doc.page_count

        for batch_start in range(0, total_pages, self.CHUNK_SIZE):
            batch_end = min(batch_start + self.CHUNK_SIZE, total_pages)

            # 处理当前批次
            batch_results = []
            for page_num in range(batch_start, batch_end):
                page = doc.load_page(page_num)

                # 转换为图像
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")

                # 版面分析
                layout = await self.analyze_layout(img_bytes)

                # 内容提取
                content = await self.extract_content(img_bytes, layout)

                batch_results.append(PageResult(
                    page_num=page_num + 1,
                    layout=layout,
                    content=content,
                ))

                # 释放页面内存
                del page, pix

            yield BatchResult(
                batch_start=batch_start,
                batch_end=batch_end,
                pages=batch_results,
            )

        doc.close()
```

### 3.2 版面分析模型选型

| 模型 | 参数量 | 速度 | 精度 | 推荐场景 |
|:-----|:------:|:----:|:----:|:---------|
| **YOLO-DocLayout** | 11M | ⚡⚡⚡ | ⭐⭐⭐ | 高吞吐量场景 |
| **LayoutLMv3** | 125M | ⚡⚡ | ⭐⭐⭐⭐ | 复杂版面 |
| **DiT (Document Image Transformer)** | 300M | ⚡ | ⭐⭐⭐⭐⭐ | 高精度需求 |
| **PP-StructureV2** | 自定义 | ⚡⚡⚡ | ⭐⭐⭐⭐ | 中文优化 |

**推荐方案**:
- 初筛: YOLO-DocLayout (快速分类)
- 精细: LayoutLMv3 (复杂页面)
- 表格: TableTransformer (专用)

### 3.3 表格处理流程

```python
class TableProcessor:
    """
    表格检测与结构化提取
    """

    async def process_table(
        self,
        img_bytes: bytes,
        bbox: list[float]
    ) -> TableResult:
        """
        表格处理流程:
        1. 区域裁剪
        2. 结构检测 (行/列边界)
        3. 单元格 OCR
        4. 合并输出
        """
        # 1. 裁剪表格区域
        table_img = self._crop_region(img_bytes, bbox)

        # 2. 检测表格结构
        structure = await self.detect_structure(table_img)
        # structure: {rows: [...], cols: [...], cells: [...]}

        # 3. OCR 每个单元格
        cells_content = []
        for cell in structure['cells']:
            cell_img = self._crop_region(table_img, cell['bbox'])
            text = await self.ocr_engine.recognize(cell_img)
            cells_content.append({
                'row': cell['row'],
                'col': cell['col'],
                'rowspan': cell.get('rowspan', 1),
                'colspan': cell.get('colspan', 1),
                'text': text,
            })

        # 4. 生成 Markdown 表格
        markdown = self._to_markdown(cells_content, structure)

        return TableResult(
            cells=cells_content,
            markdown=markdown,
            csv=self._to_csv(cells_content),
            confidence=structure['confidence'],
        )
```

### 3.4 图像/漫画处理

```python
class VisualContentProcessor:
    """
    图像和漫画内容理解
    """

    async def process_visual(
        self,
        img_bytes: bytes,
        content_type: Literal["image", "figure", "chart", "comic"]
    ) -> VisualResult:
        """
        根据内容类型选择处理策略
        """
        if content_type == "chart":
            # 图表: 提取数据趋势
            return await self._process_chart(img_bytes)

        elif content_type == "comic":
            # 漫画: 检测对话气泡 + OCR + 场景描述
            return await self._process_comic(img_bytes)

        else:
            # 通用图像: VLM 描述
            return await self._process_image(img_bytes)

    async def _process_comic(self, img_bytes: bytes) -> VisualResult:
        """
        漫画处理:
        1. 分格检测 (Panel Detection)
        2. 对话气泡检测
        3. 气泡内文字 OCR
        4. 场景描述
        """
        # 分格检测
        panels = await self.panel_detector.detect(img_bytes)

        results = []
        for panel in panels:
            panel_img = self._crop(img_bytes, panel['bbox'])

            # 气泡检测
            bubbles = await self.bubble_detector.detect(panel_img)

            # OCR 气泡文字
            dialogues = []
            for bubble in bubbles:
                bubble_img = self._crop(panel_img, bubble['bbox'])
                text = await self.ocr_engine.recognize(bubble_img)
                dialogues.append(text)

            # VLM 场景描述 (排除气泡区域)
            scene = await self.vlm.describe(
                panel_img,
                mask_regions=[b['bbox'] for b in bubbles]
            )

            results.append({
                'panel_id': panel['id'],
                'dialogues': dialogues,
                'scene': scene,
            })

        return VisualResult(panels=results)
```

---

## 4. 分布式处理架构

### 4.1 任务分解策略

```
原始 PDF 任务
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    任务分解 (Task Decomposition)                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ├──▶ 文档级任务 (Document Tasks)
    │       • 元数据提取
    │       • 整体质量评估
    │       • 目录提取
    │
    ├──▶ 页面级任务 (Page Tasks) ← 主要并行点
    │       • 版面分析
    │       • 文本提取
    │       • 图像提取
    │
    └──▶ 区域级任务 (Region Tasks)
            • 表格结构化
            • 图像理解
            • 复杂公式识别
```

### 4.2 Ray 分布式实现

```python
import ray
from ray import serve

@ray.remote(num_gpus=1)
class PDFPageProcessor:
    """
    GPU Worker: 处理单页 PDF
    """

    def __init__(self):
        self.layout_model = self._load_layout_model()
        self.ocr_engine = self._load_ocr_engine()
        self.vlm = self._load_vlm()

    def process_page(self, page_img: bytes, page_num: int) -> dict:
        # 版面分析
        layout = self.layout_model.predict(page_img)

        # 并行提取各区域
        results = []
        for region in layout['regions']:
            if region['type'] == 'text':
                text = self.ocr_engine.recognize(region['image'])
                results.append({'type': 'text', 'content': text})
            elif region['type'] == 'table':
                table = self.table_processor.extract(region['image'])
                results.append({'type': 'table', 'content': table})
            elif region['type'] in ('figure', 'chart', 'comic'):
                desc = self.vlm.describe(region['image'])
                results.append({'type': region['type'], 'content': desc})

        return {
            'page_num': page_num,
            'regions': results,
            'layout': layout,
        }


class PDFBatchProcessor:
    """
    批量 PDF 处理协调器
    """

    def __init__(self, num_workers: int = 8):
        ray.init(ignore_reinit_error=True)
        self.workers = [PDFPageProcessor.remote() for _ in range(num_workers)]

    async def process_pdf(self, pdf_path: str) -> list[dict]:
        """
        并行处理 PDF 所有页面
        """
        # 1. 提取所有页面图像
        page_images = self._extract_pages(pdf_path)

        # 2. 分配任务到 workers
        futures = []
        for i, (page_num, page_img) in enumerate(page_images):
            worker = self.workers[i % len(self.workers)]
            future = worker.process_page.remote(page_img, page_num)
            futures.append(future)

        # 3. 收集结果
        results = ray.get(futures)
        return sorted(results, key=lambda x: x['page_num'])
```

### 4.3 资源估算

| 配置 | 数值 | 说明 |
|:-----|:-----|:-----|
| **GPU 节点** | 8~16 × A100 (80GB) | 版面分析 + VLM |
| **CPU 节点** | 32~64 核 × 4 节点 | 预处理 + OCR |
| **内存** | 256GB/节点 | 缓存页面图像 |
| **存储 IOPS** | 100K+ | OSS 并发读取 |
| **处理速度** | ~1000 页/分钟/GPU | 估算 |
| **总耗时** | ~14~30 天 | 100~500TB 全量 |

---

## 5. 质量控制

### 5.1 质量评估指标

```python
class QualityScorer:
    """
    文档处理质量评分
    """

    def score(self, page_result: PageResult) -> QualityScore:
        scores = {}

        # 1. OCR 置信度
        scores['ocr_confidence'] = self._ocr_confidence(page_result)

        # 2. 布局完整性 (检测到的区域 vs 页面面积)
        scores['layout_coverage'] = self._layout_coverage(page_result)

        # 3. 表格结构一致性
        scores['table_validity'] = self._table_validity(page_result)

        # 4. 内容连贯性 (段落间/跨页)
        scores['coherence'] = self._text_coherence(page_result)

        # 5. 综合评分
        overall = (
            scores['ocr_confidence'] * 0.3 +
            scores['layout_coverage'] * 0.2 +
            scores['table_validity'] * 0.3 +
            scores['coherence'] * 0.2
        )

        return QualityScore(
            overall=overall,
            details=scores,
            needs_review=overall < 0.7,  # 低于阈值需人工复核
        )
```

### 5.2 人工复核流程

```
低质量页面 (score < 0.7)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    人工复核队列                                   │
├─────────────────────────────────────────────────────────────────┤
│ 优先级排序:                                                      │
│ 1. 表格识别失败 (表格数据价值高)                                  │
│ 2. OCR 置信度极低 (<0.5)                                         │
│ 3. 布局检测异常                                                  │
│ 4. 其他                                                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    标注平台 (Label Studio)                        │
├─────────────────────────────────────────────────────────────────┤
│ • 表格边界校正                                                   │
│ • OCR 文本修正                                                   │
│ • 区域类型重标注                                                 │
│ • 阅读顺序调整                                                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
反馈到模型微调 (Active Learning)
```

---

## 6. 实施路线图

### Phase 1: 基础设施 (2 周)

- [ ] Ray 集群搭建
- [ ] GPU 节点配置 (CUDA/cuDNN)
- [ ] OSS ↔ 计算节点高速通道
- [ ] 监控告警 (Prometheus + Grafana)

### Phase 2: 核心模型部署 (2 周)

- [ ] 版面分析模型 (YOLO/LayoutLMv3) 部署
- [ ] OCR 引擎 (PP-OCRv4) 部署
- [ ] 表格识别模型 (TableTransformer) 部署
- [ ] VLM 服务 (Qwen-VL) 部署

### Phase 3: 管道集成 (2 周)

- [ ] 流式处理器开发
- [ ] 分布式任务调度
- [ ] 质量评估模块
- [ ] 增量索引接口

### Phase 4: 规模化处理 (持续)

- [ ] 小批量验证 (1TB)
- [ ] 中批量测试 (10TB)
- [ ] 全量处理 (100~500TB)
- [ ] 持续监控与优化

---

## 7. 技术选型总结

| 组件 | 推荐方案 | 备选方案 |
|:-----|:---------|:---------|
| **任务调度** | Ray | Celery + Redis |
| **PDF 解析** | PyMuPDF | pdf2image + Poppler |
| **版面分析** | PP-StructureV2 | LayoutLMv3, DiT |
| **文本 OCR** | PP-OCRv4 | EasyOCR, PaddleOCR |
| **表格识别** | TableTransformer | CascadeTabNet |
| **VLM** | Qwen-VL-Max | GPT-4V, DeepSeek-VL |
| **向量数据库** | Qdrant 集群 | Milvus, Weaviate |
| **全文检索** | Elasticsearch | OpenSearch |

---

*文档版本: v1.0*
*创建时间: 2025-12-08*
