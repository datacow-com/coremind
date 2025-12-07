"""
PDF ingestion is handled by the unified LangGraph pipeline (create_ingest_graph).
This file now only provides a thin alias to keep imports stable.
"""

from core.ingestion.graph import create_ingest_graph


def create_pdf_index_ingest_graph():
    return create_ingest_graph()
