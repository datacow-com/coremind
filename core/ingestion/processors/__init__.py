"""
Processing modules for specialized data types.

This package contains processors for:
- Video understanding (VideoProcessor)
- Excel analysis (ExcelProcessor)
- Comic recognition (ComicProcessor)
"""

from core.ingestion.processors.comic_processor import ComicProcessor
from core.ingestion.processors.excel_processor import ExcelProcessor
from core.ingestion.processors.video_processor import VideoProcessor

__all__ = [
    "ComicProcessor",
    "ExcelProcessor",
    "VideoProcessor",
]
