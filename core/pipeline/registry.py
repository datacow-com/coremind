from typing import Any


def get_pipeline_registry() -> list[dict[str, Any]]:
    """
    Registry of actually supported pipelines.
    Remove unsupported ragflow templates to avoid false expectations.
    """
    return [
        {
            "id": "visual_pdf_general",
            "name": "Visual PDF → Markdown",
            "description": "PDF 转图片，经 VLM 提取结构化 Markdown",
            "input_types": [".pdf"],
        },
        {
            "id": "pdf_index",
            "name": "PDF → 索引",
            "description": "PDF 版面解析与分块，写入向量/关键词索引",
            "input_types": [".pdf"],
        },
        {
            "id": "image_to_md",
            "name": "Image → Markdown",
            "description": "图片经 VLM 转 Markdown，并可入索引",
            "input_types": [".png", ".jpg", ".jpeg"],
        },
        {
            "id": "html_to_md",
            "name": "HTML → Markdown",
            "description": "HTML 清洗并转换为 Markdown",
            "input_types": [".html"],
        },
    ]
