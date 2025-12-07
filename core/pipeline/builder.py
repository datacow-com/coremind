from core.ingestion.graph import create_ingest_graph


def create_ingest_graph_for_kb(kb_name: str | None, file_path: str | None):
    # 统一使用新 LangGraph 管线，避免双重实现
    return create_ingest_graph()
