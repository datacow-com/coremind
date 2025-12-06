import os
from typing import Any

from core.ingestion.graph import create_ingest_graph
from core.ingestion import create_ingest_graph as create_legacy_ingest_graph
from core.ingestion.docx_ingest import create_docx_ingest_graph
from core.ingestion.eml_ingest import create_eml_ingest_graph
from core.ingestion.html_ingest import create_html_ingest_graph
from core.ingestion.image_ingest import create_image_ingest_graph
from core.ingestion.markdown_ingest import create_markdown_ingest_graph
from core.ingestion.md_index_ingest import create_md_index_ingest_graph
from core.ingestion.pdf_index_ingest import create_pdf_index_ingest_graph
from core.ingestion.pptx_ingest import create_pptx_ingest_graph
from core.ingestion.xlsx_ingest import create_xlsx_ingest_graph
from core.storage.kb_config import load_kb_config


def create_ingest_graph_for_kb(kb_name: str | None, file_path: str | None):
    ext = os.path.splitext(file_path or "")[1].lower() or ""
    cfg: dict[str, Any] = {}
    if kb_name:
        try:
            cfg = load_kb_config(str(kb_name)) or {}
        except Exception:
            cfg = {}
    
    # Check if using new pipeline strategy
    use_new_pipeline = cfg.get("use_new_pipeline", True)
    
    if use_new_pipeline:
        # For PDF/Images, route to new unified graph
        if ext in {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            return create_ingest_graph()
    
    selected = (cfg.get("ingestion_pipeline") or {}).get("selected_pipeline") or ""
    if ext == ".pdf":
        if selected == "pdf_index":
            return create_pdf_index_ingest_graph()
        return create_legacy_ingest_graph()
    if ext in {".png", ".jpg", ".jpeg"}:
        return create_image_ingest_graph()
    if ext == ".md":
        if selected == "markdown_index":
            return create_md_index_ingest_graph()
        return create_markdown_ingest_graph()
    if ext == ".docx":
        return create_docx_ingest_graph()
    if ext == ".pptx":
        return create_pptx_ingest_graph()
    if ext == ".xlsx":
        return create_xlsx_ingest_graph()
    if ext == ".html":
        return create_html_ingest_graph()
    if ext == ".eml":
        return create_eml_ingest_graph()
    return create_markdown_ingest_graph()
