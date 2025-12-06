import json
import os
from typing import Any

from server.config import settings


def _kb_dir() -> str:
    base = settings.uploads_dir_resolved
    path = os.path.join(base, "knowledgebase")
    os.makedirs(path, exist_ok=True)
    return path


def kb_config_path(name: str) -> str:
    return os.path.join(_kb_dir(), f"{name}.json")


def default_kb_config(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "stack": "cn",  # cn or en
        "description": "",
        "tags": [],
        "visibility": "private",  # private/org/public
        "embedding_model": None,
        "method": "light",  # light/deep
        "entity_types": ["organization", "person", "geo", "event", "category"],
        "entity_normalize": False,
        "section_generate": False,
        "outline_strategy": "whole",  # whole/file
        # retrieval & index overrides
        "top_k_default": getattr(settings, "top_k_default", 5),
        "candidate_k": getattr(settings, "candidate_k", 50),
        "vector_weight": getattr(settings, "vector_weight", 0.6),
        "keyword_weight": getattr(settings, "keyword_weight", 0.4),
        "rrf_k": getattr(settings, "rrf_k", 60),
        "reranker_filter_threshold": getattr(settings, "reranker_filter_threshold", 0.2),
        "grade_threshold": getattr(settings, "grade_threshold", 0.5),
        "hallucination_threshold": getattr(settings, "hallucination_threshold", 0.5),
        # vector store backend per KB
        "vector_backend": None,
        "collection_name": None,
        # web search capability (KB-level override)
        "web_search_enabled": bool(getattr(settings, "web_search_enabled", True)),
        "web_search_provider": getattr(settings, "web_search_provider", None),
        # ingestion pipeline (built-in, configurable)
        "ingestion_pipeline": {
            "enabled": True,
            "template": "general",
            "semantic_chunking": bool(getattr(settings, "semantic_chunking", False)),
            "parser_denoise": bool(getattr(settings, "parser_denoise", False)),
            "vlm_enabled": True,
            "vision_provider": getattr(settings, "vision_provider", None),
            "layoutlm_enabled": bool(getattr(settings, "layoutlm_enabled", False)),
            "yolo_enabled": bool(getattr(settings, "yolo_enabled", False)),
            "selected_pipeline": None,
        },
        # chunking strategy
        "chunk_strategy": {
            "min_tokens": 120,
            "max_tokens": 600,
            "chunk_overlap": 50,
            "merge_small": True,
            "semantic_enabled": False,
            "semantic_threshold": 0.72,
            "keep_layout": True,
            "keep_bbox": True,
            "table_extract": True,
            "ocr_enabled": False,
        },
        "knowledge_graph": {
            "enabled": False,
            "status": "idle",
        },
        "raptor": {
            "enabled": False,
            "scope": "whole",  # whole | file
            "prompt": "",
            "status": "idle",
            "max_tokens": 256,
            "threshold": 0.1,
            "max_clusters": 64,
            "seed": 0,
            "file_id": None,
        },
        "data_sources": [],
    }


def load_kb_config(name: str) -> dict[str, Any]:
    path = kb_config_path(name)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as err:
            print(f"[warn] kb_config load failed for {name}: {err}")
    return default_kb_config(name)


def save_kb_config(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    base = default_kb_config(name)
    base.update({k: v for k, v in (cfg or {}).items() if v is not None})
    path = kb_config_path(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    return base
