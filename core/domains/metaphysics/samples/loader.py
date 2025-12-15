"""
Sample Loader - 样本加载器

Phase 2: 垂直领域增强
提供命理测试样本的加载功能。
"""
import json
from pathlib import Path
from typing import Any


def load_text_samples() -> list[dict[str, Any]]:
    """
    加载所有文本样本
    
    Returns:
        list[dict]: 样本列表，每个样本包含 id, description, content, expected
    """
    samples_dir = Path(__file__).parent
    all_samples: list[dict[str, Any]] = []
    
    # 加载主样本文件
    main_file = samples_dir / "text_samples.json"
    if main_file.exists():
        with open(main_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_samples.extend(data.get("samples", []))
    
    # 加载扩展样本文件
    extended_file = samples_dir / "text_samples_extended.json"
    if extended_file.exists():
        with open(extended_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            all_samples.extend(data.get("samples", []))
    
    return all_samples


def load_image_samples() -> list[dict[str, Any]]:
    """
    加载图像样本
    
    Returns:
        list[dict]: 图像样本列表，每个样本包含 path, expected
    """
    samples_dir = Path(__file__).parent / "images"
    if not samples_dir.exists():
        return []
    
    samples: list[dict[str, Any]] = []
    for img_path in samples_dir.glob("*.png"):
        meta_path = img_path.with_suffix(".json")
        expected = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                expected = json.load(f)
        samples.append({
            "path": str(img_path),
            "expected": expected,
        })
    
    return samples


def get_sample_by_id(sample_id: int) -> dict[str, Any] | None:
    """
    根据 ID 获取样本
    
    Args:
        sample_id: 样本 ID
        
    Returns:
        dict | None: 样本数据，未找到返回 None
    """
    samples = load_text_samples()
    for sample in samples:
        if sample.get("id") == sample_id:
            return sample
    return None
