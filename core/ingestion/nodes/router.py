from core.state import IngestState

class RouterNode:
    async def __call__(self, state: IngestState) -> IngestState:
        # No-op, just a passthrough for logic in conditional edges
        return state

def route_file(state: IngestState) -> str:
    cfg = state['strategy_config']
    
    # 1. Forced OCR
    if cfg.get('force_ocr', False):
        return "gpu_parser"
    
    # 2. Image types
    if state['file_type'] in ['jpg', 'jpeg', 'png', 'tiff', 'bmp']:
        return "gpu_parser"
        
    # 3. PDF types (Scanned check?)
    if state['file_type'] == 'pdf':
        # Basic heuristic: If we wanted to check if scanned, we'd need to inspect raw_content 
        # or use a lightweight detector. 
        # For MVP, assume CPU unless forced.
        return "cpu_parser"
        
    # Default CPU
    return "cpu_parser"

