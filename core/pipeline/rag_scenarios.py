from typing import Any


def get_rag_scenario_pipelines() -> list[dict[str, Any]]:
    """
    Limit to actually supported ingestion templates to avoid false promises.
    """
    return [
        # 与 /api/ingest/scenarios 对齐，仅保留现阶段支持的内置场景
        {"id": "laws", "name": "Laws", "category": "rag", "description": "法规/条例精读与条款检索"},
        {
            "id": "paper",
            "name": "Paper",
            "category": "rag",
            "description": "论文长文分块与摘要检索",
        },
        {"id": "table", "name": "Table", "category": "rag", "description": "表格优先解析与入索引"},
        {"id": "html", "name": "HTML", "category": "rag", "description": "网页/HTML 清洗与分块"},
    ]
