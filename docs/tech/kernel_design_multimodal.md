# OmniRAG Kernel Design: Multi-modal Retrieval & Table Strategy

## 1. Table Processing Strategy
Tables are first-class citizens in OmniRAG.

### 1.1 Ingestion
- **Detection**: Use LayoutLMv3 (via GpuVisionParser) or heuristics (CpuTextParser) to detect table bounding boxes.
- **Extraction**: 
    - CPU: Extract text layout, convert to Markdown/CSV format.
    - GPU: OCR table cell content, reconstruct structure.
- **Chunking (Table-First Strategy)**:
    - `SmartChunker(mode='table_first')`: Tables are extracted as standalone chunks.
    - **Metadata**: `block_type='table'`, `bbox` preserved.
    - **Representation**: 
        - Text Content: Markdown representation of table.
        - Summary: LLM generates a 1-sentence summary of table content (appended to content for dense retrieval).

### 1.2 Retrieval
- **Query Intent**: `QueryPreProcessor` detects if user asks for "stats", "comparison", or explicit "table".
- **Filtering**: If intent is "table_query", add filter `metadata.block_type == 'table'`.
- **Ranking**: Boost score of Table chunks in RRF fusion if intent matches.

## 2. Image Processing Strategy (Diagrams/Charts)

### 2.1 Ingestion
- **Extraction**: `GpuVisionParser` extracts images (Figure, Chart).
- **Description**: 
    - Use VLM (Qwen-VL) to generate a dense caption/description of the image.
    - Store description in `content` field for vectorization.
- **Chunking**: Standalone chunk for each figure.
- **Metadata**: `block_type='image'`, `image_path` (link to object store).

### 2.2 Retrieval
- **Vector Search**: Matches query against Image Description.
- **Response**: Return Image Chunk. Frontend renders the image using `image_path` (signed URL).

## 3. Mixed-Modal Retrieval (The "Omni" part)
- **Fusion**: 
    - Dense Vector (Text + Image Desc + Table Summary)
    - Sparse (Keywords in Table/Text)
- **Citations**: 
    - Text citation: Highlights text span.
    - Table citation: Highlights table bbox.
    - Image citation: Displays image thumbnail.

## 4. Implementation Roadmap (Kernel)
- [ ] Implement `TableExtractor` helper in `core/vision/table.py`.
- [ ] Implement `ImageCaptioner` node using VLM.
- [ ] Update `SmartChunker` to support `table_first` logic.
- [ ] Update `HybridRetriever` to apply dynamic filters based on Intent.

