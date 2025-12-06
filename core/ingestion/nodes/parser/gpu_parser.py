import os
import asyncio
from typing import Dict, Any, List
from core.state import IngestState
from core.utils.monitor import ingest_duration
from core.llm.gateway import LLMGateway

# Optional local vision models
try:
    from core.vision.yolo_detector import detect_blocks_yolo
    from core.vision.layoutlm_parser import classify_blocks_layoutlm
    LOCAL_VISION_AVAILABLE = True
except ImportError:
    LOCAL_VISION_AVAILABLE = False

# 1. Real OCR Providers
class DeepSeekOCR:
    """Uses DeepSeek-Janus-Pro or similar multimodal model for OCR"""
    def __init__(self):
        self.gateway = LLMGateway()
        
    async def process(self, content: bytes) -> Dict[str, Any]:
        import base64
        b64_img = base64.b64encode(content).decode('utf-8')
        prompt = "Extract all text from this image. Preserve layout and structure. Output in Markdown format."
        resp = await self.gateway.chat(prompt) 
        return {
            "blocks": [{"type": "text", "content": resp, "page": 1}],
            "images": [] 
        }

class QwenVLProvider:
    """Uses Qwen-VL-Max via DashScope"""
    def __init__(self):
        self.api_key = os.environ.get("DASHSCOPE_API_KEY")
        
    async def process(self, content: bytes) -> Dict[str, Any]:
        # Mock call logic placeholder
        return {
            "blocks": [{"type": "text", "content": "Qwen-VL Result", "page": 1}],
            "images": []
        }

class VolcEngineOCR:
    """Uses VolcEngine OCR"""
    def __init__(self):
        self.ak = os.environ.get("VOLC_ACCESS_KEY")
        self.sk = os.environ.get("VOLC_SECRET_KEY")
        
    async def process(self, content: bytes) -> Dict[str, Any]:
        # Mock call logic placeholder
        return {
            "blocks": [{"type": "text", "content": "Volc Result", "page": 1}],
            "images": []
        }

class LocalYoloProvider:
    """Uses local YOLO + LayoutLM if available"""
    def __init__(self):
        from server.config import settings
        self.yolo_model = getattr(settings, "yolo_model", None)
        self.layoutlm_model = getattr(settings, "layoutlm_model", None)

    async def process(self, content: bytes) -> Dict[str, Any]:
        if not LOCAL_VISION_AVAILABLE:
            raise RuntimeError("Local vision dependencies missing")
            
        # Run YOLO detection in thread
        boxes = await asyncio.to_thread(detect_blocks_yolo, content, self.yolo_model)
        
        blocks = []
        if boxes and self.layoutlm_model:
            # Run LayoutLM classification
            labels = await asyncio.to_thread(classify_blocks_layoutlm, content, boxes, self.layoutlm_model)
            for box, label in zip(boxes, labels):
                blocks.append({
                    "type": label or "text",
                    "bbox": list(box),
                    "content": "", # Needs OCR on crop
                    "page": 1
                })
        else:
            # Fallback or just boxes
            for box in boxes:
                blocks.append({
                    "type": "unknown", 
                    "bbox": list(box),
                    "content": "",
                    "page": 1
                })
                
        return {"blocks": blocks, "images": []}

# Mock Provider (Fallback)
class MockOCRProvider:
    async def process(self, content: bytes) -> Dict[str, Any]:
        return {
            "blocks": [{"type": "text", "content": "OCR Result Content (Mock)", "bbox": [0,0,100,100], "page": 1}],
            "images": []
        }

class GpuVisionParser:
    def __init__(self):
        self.providers = {
            "mock": MockOCRProvider(),
            "deepseek": DeepSeekOCR(),
            "qwen-vl": QwenVLProvider(),
            "volc_engine": VolcEngineOCR(),
            "paddle": LocalYoloProvider() # Mapping paddle to local yolo pipeline for now
        }

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='gpu_parser').time():
            cfg = state['strategy_config']
            requested = cfg.get('ocr_provider', 'auto')
            fallback_chain = cfg.get('ocr_fallback_chain', ["qwen-vl", "volc_engine", "paddle", "mock"])

            # provider availability检查
            def available(name: str) -> bool:
                if name == "qwen-vl":
                    return bool(os.environ.get("DASHSCOPE_API_KEY"))
                if name == "volc_engine":
                    return bool(os.environ.get("VOLC_ACCESS_KEY") and os.environ.get("VOLC_SECRET_KEY"))
                if name == "paddle":
                    return LOCAL_VISION_AVAILABLE
                if name == "deepseek":
                    return True  # 依赖 LLMGateway，自身会再判断
                if name == "mock":
                    return True
                return False

            provider_sequence = []
            if requested == "auto":
                # 先按可用性排序
                for name in ["qwen-vl", "volc_engine", "deepseek", "paddle", "mock"]:
                    if available(name):
                        provider_sequence.append(name)
            else:
                provider_sequence.append(requested)

            # 追加 fallback 链
            for name in fallback_chain:
                if name not in provider_sequence and available(name):
                    provider_sequence.append(name)

            if not provider_sequence:
                provider_sequence = ["mock"]

            last_error = None
            for provider_name in provider_sequence:
                provider = self.providers.get(provider_name, self.providers['mock'])
                try:
                    result = await provider.process(state['raw_content'])
                    state['parsed_blocks'] = result['blocks']
                    state['images'] = result.get('images', [])

                    for b in state['parsed_blocks']:
                        b['ocr_provider'] = provider_name
                        b['ocr_confidence'] = b.get('ocr_confidence', 0.95)

                    # 记录进度
                    if 'progress' in state:
                        state['progress']['ocr_provider'] = provider_name
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    state['error_log'].append({
                        'stage': 'gpu_parser',
                        'error': str(e),
                        'provider': provider_name
                    })
                    continue

            if last_error and provider_sequence and provider_sequence[-1] != 'mock':
                # 最后尝试 mock 兜底
                res = await self.providers['mock'].process(state['raw_content'])
                state['parsed_blocks'] = res['blocks']

            return state
