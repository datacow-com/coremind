import json
import os
from typing import Any

from core.storage.kb_config_db import load_kb, save_kb
from server.config import settings


def default_kb_config(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "stack": "cn",
        "description": "",
        "tags": [],
        "visibility": "private",
        "embedding_model": None,
        "method": "light",
        "entity_types": ["organization", "person", "geo", "event", "category"],
        "entity_normalize": False,
        "section_generate": False,
        "outline_strategy": "whole",
        "top_k_default": getattr(settings, "top_k_default", 5),
        "candidate_k": getattr(settings, "candidate_k", 50),
        "vector_weight": getattr(settings, "vector_weight", 0.6),
        "keyword_weight": getattr(settings, "keyword_weight", 0.4),
        "rrf_k": getattr(settings, "rrf_k", 60),
        "reranker_filter_threshold": getattr(settings, "reranker_filter_threshold", 0.2),
        "grade_threshold": getattr(settings, "grade_threshold", 0.5),
        "hallucination_threshold": getattr(settings, "hallucination_threshold", 0.5),
        "vector_backend": None,
        "collection_name": None,
        "web_search_enabled": bool(getattr(settings, "web_search_enabled", True)),
        "web_search_provider": getattr(settings, "web_search_provider", None),
        # ═══════════════════════════════════════════════════════════════════
        # 能力配置 (Capabilities) - 可见、可选、可配、可用
        # ═══════════════════════════════════════════════════════════════════
        "capabilities": {
            # 基础能力 (默认启用)
            "basic": {
                "text_extraction": True,
                "chunking": {
                    "enabled": True,
                    "mode": "fixed",
                    "chunk_size": 512,
                    "overlap": 50,
                },
                "embedding": {
                    "enabled": True,
                    "model": "BAAI/bge-m3",
                },
            },
            # 增强能力 (可选)
            "enhanced": {
                "table_recognition": {
                    "enabled": False,
                    "model": "table_transformer",
                    "output_format": "markdown",
                },
                "ocr": {
                    "enabled": False,
                    "engine": "paddleocr",
                    "languages": ["zh", "en"],
                },
                "image_understanding": {
                    "enabled": False,
                    "vlm_provider": "qwen-vl",
                    "detail_level": "detailed",
                },
                "semantic_chunking": {
                    "enabled": False,
                },
                "reranking": {
                    "enabled": True,
                    "provider": "cross_encoder",
                },
            },
            # 专业能力 (按需)
            "pro": {
                "video_understanding": {
                    "enabled": False,
                },
                "excel_analysis": {
                    "enabled": False,
                },
                "comic_recognition": {
                    "enabled": False,
                },
                "layout_analysis": {
                    "enabled": False,
                },
            },
            # 高级能力 (知识增强)
            "advanced": {
                "raptor": {
                    "enabled": False,
                    "scope": "whole_kb",
                    "max_clusters": 64,
                    "levels": 3,
                },
                "graphrag": {
                    "enabled": False,
                    "entity_types": ["person", "organization", "geo", "event"],
                    "community_detection": True,
                },
                "multimodal_retrieval": {
                    "enabled": False,
                },
                "hallucination_detection": {
                    "enabled": False,
                },
                "web_search": {
                    "enabled": False,
                    "provider": "tavily",
                },
            },
        },
        # Legacy 字段 (向后兼容)
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
        "knowledge_graph": {"enabled": False, "status": "idle"},
        "raptor": {
            "enabled": False,
            "scope": "whole",
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
    db_cfg = load_kb(name)
    if db_cfg is not None:
        base = default_kb_config(name)
        base.update(db_cfg or {})
        return base
    # fallback to local file if DB unavailable
    try:
        base_dir = settings.uploads_dir_resolved
        path = os.path.join(base_dir, "knowledgebase", f"{name}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                base = default_kb_config(name)
                base.update(data or {})
                return base
    except Exception:
        pass
    return default_kb_config(name)


def save_kb_config(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    base = default_kb_config(name)
    base.update({k: v for k, v in (cfg or {}).items() if v is not None})
    try:
        save_kb(name, base)
        return base
    except Exception:
        # fallback to file
        try:
            base_dir = settings.uploads_dir_resolved
            kb_dir = os.path.join(base_dir, "knowledgebase")
            os.makedirs(kb_dir, exist_ok=True)
            path = os.path.join(kb_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return base
