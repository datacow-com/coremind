from typing import Any


def get_rag_scenario_pipelines() -> list[dict[str, Any]]:
    """
    Limit to actually supported ingestion templates to avoid false promises.
    """
    return [
        {"id": "naive", "name": "Naive", "category": "rag", "description": "通用纯文本解析与分块"},
        {
            "id": "qa",
            "name": "QA",
            "category": "rag",
            "description": "问答型语料解析与问答意图优化",
        },
        {
            "id": "manual",
            "name": "Manual",
            "category": "rag",
            "description": "手册/说明书解析，层级标题与目录对齐",
        },
        {
            "id": "table",
            "name": "Table",
            "category": "rag",
            "description": "表格数据抽取与标准化 Markdown 表格",
        },
        {
            "id": "presentation",
            "name": "Presentation",
            "category": "rag",
            "description": "PPT 幻灯片：标题与要点解析",
        },
        {
            "id": "picture",
            "name": "Picture",
            "category": "rag",
            "description": "图片转 Markdown 及图文说明抽取",
        },
        {"id": "one", "name": "One", "category": "rag", "description": "单页/短文档解析"},
        {
            "id": "email",
            "name": "Email",
            "category": "rag",
            "description": "邮件场景：头部字段、正文与附件描述解析",
        },
    ]
