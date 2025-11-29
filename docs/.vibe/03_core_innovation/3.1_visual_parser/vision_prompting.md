# Visual Parsing Strategy & Prompt Engineering

## Pipeline Overview
1. **Render**: PDF Page -> High-Res Image (300 DPI).
2. **Detect**: Use local generic object detection (YOLO/LayoutLM) to find `Table` and `Figure` bounding boxes.
3. **Crop & Reason**: 
   - Crop the `Table` region.
   - Send to Gemini 3 Vision.
4. **Merge**: Replace the image region in the text stream with the Markdown output from Gemini.

## Gemini 3 Vision Prompt (System Prompt)
**Role**: You are a specialized document digitizer.
**Input**: An image of a document table.
**Task**: Convert this image into a strictly formatted Markdown table.
**Constraints**:
- Do not interpret the data, just transcribe.
- Merge cells must be represented using HTML `rowspan`/`colspan` if Markdown table syntax fails, otherwise use standard pipe `|` syntax.
- If a number is `1,000.00`, keep the formatting exactly.

## Code Structure Hint
Class `VisualPDFLoader(BaseLoader)`:
- `lazy_load()` -> Yields `Document` objects.
- `_extract_table(image: PIL.Image) -> str`: Calls Gemini API.