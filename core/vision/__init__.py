"""
Vision processing modules for document understanding.

This package contains:
- LayoutAnalyzer: Complex document layout analysis
- analyze_blocks: OpenCV-based layout block detection
- (Future) ChartRecognizer: Chart and diagram understanding
"""

from core.vision.layout_analyzer import (
    LayoutAnalyzer,
    LayoutElement,
    analyze_blocks,
    create_layout_analyzer,
)

__all__ = [
    "LayoutAnalyzer",
    "LayoutElement",
    "analyze_blocks",
    "create_layout_analyzer",
]
