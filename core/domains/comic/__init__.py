"""
Comic Domain - 漫画领域解读器

Phase 2: 垂直领域增强
提供漫画分析能力，支持分格检测、对话提取、场景描述和故事叙事构建。
"""

from core.domains.comic.interpreter import ComicInterpreter
from core.domains.comic.panel_detector import PanelDetector

__all__ = [
    "ComicInterpreter",
    "PanelDetector",
]
