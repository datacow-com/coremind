# Core Unique Value: Visual-Native Parsing & Adaptive RAG

## Innovation A: `VisualPDFLoader` (The Parser)

**Problem**: Open source loaders break tables and multi-column layouts.
**Solution**: Treat documents as images, not text streams.

**Implementation Logic**:

1. **Render**: Convert PDF page $i$ to High-Res Image $I_i$ (using `pymupdf`).
2. **Layout Detection**:
   - Use a lightweight detection model (YOLO or LayoutLM) OR Gemini Flash to identify bounding boxes for **Tables** and **Figures**.
3. **Region Processing**:
   - **Text Regions**: Use standard OCR (PaddleOCR/Tesseract) for speed.
   - **Table/Chart Regions**: Crop $I_{table}$ and send to **Gemini 3 Pro Vision** with prompt:
     > "Transcribe this table into a Markdown format. Keep structure exactly."
4. **Re-assembly**: Merge the OCR text and VLM-generated Markdown tables into a single coherent Markdown string.

## Innovation B: Self-Corrective RAG (The Graph Logic)

**Problem**: Traditional RAG hallucinates when retrieval fails.
**Solution**: A "Grader" node in LangGraph.

**Graph Flow Logic**:

1. `Retrieve` -> get Documents.
2. `Grade Documents` (LLM Call):
   - Input: User Query + Retrieved Doc.
   - Output: `yes` (relevant) / `no` (irrelevant).
3. **Conditional Edge**:
   - If > 70% docs are irrelevant -> Route to `WebSearch`.
   - If relevant -> Route to `Generate`.
4. `Hallucination Check`:
   - Before returning to user, check if Answer is grounded in Documents.
   - If not -> Retry Generation or admit ignorance.
