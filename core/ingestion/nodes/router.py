"""
Router Node - Intelligent document routing for ingestion pipeline.

Features:
- Scanned PDF detection
- File type based routing
- Configurable force OCR mode
"""

from core.state import IngestState


class RouterNode:
    """Passthrough node for routing logic in conditional edges."""
    
    async def __call__(self, state: IngestState) -> IngestState:
        return state


def _is_scanned_pdf(content: bytes) -> bool:
    """
    Lightweight scanned PDF detection.
    
    Checks if first page has minimal extractable text,
    indicating it's likely a scanned document.
    
    Returns True if PDF appears to be scanned.
    """
    if not content:
        return False
    
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=content, filetype="pdf")
        if len(doc) == 0:
            return True
        
        # Check first few pages
        pages_to_check = min(3, len(doc))
        total_chars = 0
        
        for i in range(pages_to_check):
            text = doc[i].get_text()
            total_chars += len(text.strip())
        
        doc.close()
        
        # If average chars per page < 50, likely scanned
        avg_chars = total_chars / pages_to_check
        return avg_chars < 50
        
    except ImportError:
        # PyMuPDF not available, try alternative detection
        return _fallback_scan_detection(content)
    except Exception:
        # On any error, default to assuming it might be scanned
        return True


def _fallback_scan_detection(content: bytes) -> bool:
    """
    Fallback detection when PyMuPDF is not available.
    Uses heuristics based on PDF structure.
    """
    try:
        # Simple heuristic: check for text streams in PDF
        content_str = content[:50000].decode('latin-1', errors='ignore')
        
        # Look for text stream markers
        text_indicators = ['BT', 'ET', 'Tj', 'TJ', '/F']
        text_count = sum(1 for ind in text_indicators if ind in content_str)
        
        # Look for image markers
        image_indicators = ['/Image', '/XObject', '/DCTDecode', '/FlateDecode']
        image_count = sum(1 for ind in image_indicators if ind in content_str)
        
        # If more image indicators than text, likely scanned
        return image_count > text_count * 2
        
    except Exception:
        return True


def _has_complex_layout(content: bytes) -> bool:
    """
    Detect if PDF has complex layout requiring GPU processing.
    
    Complex layouts include:
    - Multi-column text
    - Tables
    - Mixed text/image regions
    """
    try:
        import fitz
        
        doc = fitz.open(stream=content, filetype="pdf")
        if len(doc) == 0:
            return False
        
        first_page = doc[0]
        
        # Check for images
        image_list = first_page.get_images()
        if len(image_list) > 2:
            return True
        
        # Check for tables (look for many rectangular blocks)
        blocks = first_page.get_text("dict")["blocks"]
        
        # Multiple text blocks at similar x positions = multi-column
        x_positions = [b.get("bbox", [0])[0] for b in blocks if b.get("type") == 0]
        if len(set(int(x / 50) for x in x_positions)) > 2:  # Multiple columns
            return True
        
        doc.close()
        return False
        
    except Exception:
        return False


def route_file(state: IngestState) -> str:
    """
    Intelligent document routing based on file type and content analysis.
    
    Routes to:
    - gpu_parser: For scanned documents, images, complex layouts
    - cpu_parser: For native text PDFs and simple documents
    """
    cfg = state['strategy_config']
    
    # 1. Forced OCR - always use GPU
    if cfg.get('force_ocr', False):
        return "gpu_parser"
    
    # 2. Image types - always use GPU
    if state['file_type'] in ['jpg', 'jpeg', 'png', 'tiff', 'bmp', 'gif', 'webp']:
        return "gpu_parser"
        
    # 3. PDF - detect if scanned or complex layout
    if state['file_type'] == 'pdf':
        raw_content = state.get('raw_content')
        
        if raw_content:
            # Check if scanned
            if _is_scanned_pdf(raw_content):
                return "gpu_parser"
            
            # Check for complex layout (optional enhanced routing)
            if cfg.get('detect_complex_layout', False) and _has_complex_layout(raw_content):
                return "gpu_parser"
        
        # Default to CPU for native text PDFs
        return "cpu_parser"
    
    # 4. Office documents
    if state['file_type'] in ['doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx']:
        return "cpu_parser"
    
    # 5. Default to CPU parser
    return "cpu_parser"
