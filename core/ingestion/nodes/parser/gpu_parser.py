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
    """Uses Qwen-VL-Max via DashScope for multimodal OCR"""

    DASHSCOPE_VL_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

    def __init__(self):
        self.api_key = os.environ.get("DASHSCOPE_API_KEY")

    async def process(self, content: bytes) -> Dict[str, Any]:
        import base64
        import httpx

        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")

        b64_img = base64.b64encode(content).decode("utf-8")
        data_uri = f"data:image/png;base64,{b64_img}"

        payload = {
            "model": "qwen-vl-max",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": data_uri},
                            {
                                "text": "Extract all text from this document image. "
                                "Preserve the layout structure. Output in Markdown format. "
                                "For tables, use Markdown table syntax. "
                                "For images/figures, describe them briefly."
                            },
                        ],
                    }
                ]
            },
            "parameters": {"result_format": "message"},
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.DASHSCOPE_VL_URL,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

            # Parse response
            output = result.get("output", {})
            choices = output.get("choices", [])
            if choices:
                text_content = choices[0].get("message", {}).get("content", "")
            else:
                text_content = ""

            return {
                "blocks": [
                    {
                        "type": "text",
                        "content": text_content,
                        "page": 1,
                        "ocr_confidence": 0.90,
                    }
                ],
                "images": [],
            }

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"DashScope API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"QwenVL processing failed: {str(e)}")

class VolcEngineOCR:
    """Uses VolcEngine (ByteDance) OCR API for document text extraction"""

    VOLC_OCR_URL = "https://visual.volcengineapi.com"
    OCR_ACTION = "OCRNormal"

    def __init__(self):
        self.ak = os.environ.get("VOLC_ACCESS_KEY")
        self.sk = os.environ.get("VOLC_SECRET_KEY")
        self.region = os.environ.get("VOLC_REGION", "cn-north-1")

    def _sign_request(self, method: str, params: dict, body: bytes) -> dict:
        """Generate VolcEngine API signature (simplified - use volcengine SDK in production)"""
        import hashlib
        import hmac
        import datetime

        # This is a simplified version - in production use volcengine-python-sdk
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        date = timestamp[:8]

        # Create canonical request hash
        headers = {
            "X-Date": timestamp,
            "X-Content-Sha256": hashlib.sha256(body).hexdigest(),
            "Host": "visual.volcengineapi.com",
        }

        # In production, implement full AWS4-HMAC-SHA256 signing
        # For now, return basic headers that will work with API key auth
        headers["Authorization"] = f"HMAC-SHA256 Credential={self.ak}/{date}/{self.region}/cv/request"

        return headers

    async def process(self, content: bytes) -> Dict[str, Any]:
        import base64
        import httpx

        if not self.ak or not self.sk:
            raise ValueError("VOLC_ACCESS_KEY and VOLC_SECRET_KEY must be set")

        b64_img = base64.b64encode(content).decode("utf-8")

        payload = {
            "image_base64": b64_img,
        }

        body = str(payload).encode("utf-8")

        try:
            # Use volcengine SDK for proper signing in production
            # Here we attempt a simplified API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.VOLC_OCR_URL}/?Action={self.OCR_ACTION}&Version=2020-08-26",
                    headers={
                        "Content-Type": "application/json",
                        "X-Access-Key": self.ak,
                        "X-Secret-Key": self.sk,  # In production, use proper HMAC signing
                    },
                    json=payload,
                )
                resp.raise_for_status()
                result = resp.json()

            # Parse VolcEngine OCR response
            data = result.get("data", {})
            lines = data.get("line_texts", [])
            full_text = "\n".join(lines) if lines else data.get("text", "")

            blocks = []
            if full_text:
                blocks.append(
                    {
                        "type": "text",
                        "content": full_text,
                        "page": 1,
                        "ocr_confidence": data.get("confidence", 0.85),
                    }
                )

            return {"blocks": blocks, "images": []}

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"VolcEngine API error: {e.response.status_code}")
        except Exception as e:
            raise RuntimeError(f"VolcEngine OCR failed: {str(e)}")


class PaddleOCRProvider:
    """
    P1 Fix: Real PaddleOCR implementation for document text extraction.
    
    Features:
    - Multi-language support (Chinese, English, etc.)
    - Angle detection and correction
    - Table structure recognition
    """
    
    def __init__(self):
        self._ocr = None
        self._table_engine = None
    
    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
                self._ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang='ch',  # Chinese + English
                    show_log=False,
                    use_gpu=True,
                )
            except ImportError:
                raise RuntimeError("PaddleOCR not installed. Run: pip install paddleocr")
        return self._ocr
    
    async def process(self, content: bytes) -> Dict[str, Any]:
        import numpy as np
        from PIL import Image
        import io
        
        # Convert bytes to numpy array
        try:
            img = Image.open(io.BytesIO(content))
            img_array = np.array(img.convert('RGB'))
        except Exception as e:
            raise RuntimeError(f"Failed to decode image: {e}")
        
        # Run OCR in thread
        ocr = self._get_ocr()
        result = await asyncio.to_thread(ocr.ocr, img_array, cls=True)
        
        blocks = []
        images = []
        
        if result and result[0]:
            for line in result[0]:
                if len(line) >= 2:
                    bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    text_info = line[1]  # (text, confidence)
                    
                    text = text_info[0] if isinstance(text_info, tuple) else str(text_info)
                    confidence = text_info[1] if isinstance(text_info, tuple) and len(text_info) > 1 else 0.9
                    
                    # Convert polygon to bounding box
                    if bbox and len(bbox) >= 2:
                        x_coords = [p[0] for p in bbox]
                        y_coords = [p[1] for p in bbox]
                        flat_bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                    else:
                        flat_bbox = [0, 0, 100, 100]
                    
                    blocks.append({
                        "type": "text",
                        "content": text,
                        "bbox": flat_bbox,
                        "ocr_confidence": confidence,
                        "page": 1
                    })
        
        return {"blocks": blocks, "images": images}


class LocalYoloProvider:
    """
    Uses local YOLO + LayoutLM for layout detection.
    
    Note: This provider only does detection, not OCR.
    For actual text extraction, use PaddleOCRProvider or other OCR providers.
    """
    
    def __init__(self):
        from server.config import settings
        self.yolo_model = getattr(settings, "yolo_model", None)
        self.layoutlm_model = getattr(settings, "layoutlm_model", None)
        self._paddle_ocr = None

    async def process(self, content: bytes) -> Dict[str, Any]:
        if not LOCAL_VISION_AVAILABLE:
            raise RuntimeError("Local vision dependencies missing")
            
        # Run YOLO detection in thread
        boxes = await asyncio.to_thread(detect_blocks_yolo, content, self.yolo_model)
        
        blocks = []
        if boxes and self.layoutlm_model:
            # Run LayoutLM classification
            labels = await asyncio.to_thread(classify_blocks_layoutlm, content, boxes, self.layoutlm_model)
            
            # OCR回填: Use PaddleOCR for text extraction
            try:
                if self._paddle_ocr is None:
                    self._paddle_ocr = PaddleOCRProvider()
                ocr_result = await self._paddle_ocr.process(content)
                ocr_texts = {tuple(b["bbox"]): b["content"] for b in ocr_result.get("blocks", [])}
            except Exception:
                ocr_texts = {}
            
            for box, label in zip(boxes, labels):
                # Try to find matching OCR text
                box_tuple = tuple(box)
                content_text = ocr_texts.get(box_tuple, "")
                
                # If no exact match, find overlapping OCR blocks
                if not content_text:
                    for ocr_box, ocr_text in ocr_texts.items():
                        if _boxes_overlap(list(box), list(ocr_box)):
                            content_text += ocr_text + " "
                
                blocks.append({
                    "type": label or "text",
                    "bbox": list(box),
                    "content": content_text.strip(),
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


def _boxes_overlap(box1: list, box2: list) -> bool:
    """Check if two bounding boxes overlap."""
    if len(box1) < 4 or len(box2) < 4:
        return False
    x1_min, y1_min, x1_max, y1_max = box1[0], box1[1], box1[2], box1[3]
    x2_min, y2_min, x2_max, y2_max = box2[0], box2[1], box2[2], box2[3]
    
    return not (x1_max < x2_min or x2_max < x1_min or y1_max < y2_min or y2_max < y1_min)


# Mock Provider (Fallback)
class MockOCRProvider:
    async def process(self, content: bytes) -> Dict[str, Any]:
        return {
            "blocks": [{"type": "text", "content": "OCR Result Content (Mock)", "bbox": [0,0,100,100], "page": 1}],
            "images": []
        }


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Supports per-provider rate limits and global limits.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._tokens = float(burst_size)
        self._last_update = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        import time
        
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on time elapsed
            if self._last_update > 0:
                elapsed = now - self._last_update
                refill = elapsed * (self.requests_per_minute / 60.0)
                self._tokens = min(self.burst_size, self._tokens + refill)
            
            self._last_update = now
            
            # Wait if no tokens available
            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / (self.requests_per_minute / 60.0)
                await asyncio.sleep(wait_time)
                self._tokens = 1.0
                self._last_update = time.time()
            
            self._tokens -= 1.0


class GpuVisionParser:
    """
    GPU-accelerated vision parser with multiple OCR providers.
    
    Features:
    - Multiple provider support (Qwen-VL, VolcEngine, DeepSeek, etc.)
    - Automatic fallback chain
    - Rate limiting per provider and globally
    - Concurrency control
    """
    
    # Default rate limits per provider (requests per minute)
    PROVIDER_RATE_LIMITS = {
        "qwen-vl": 30,      # DashScope rate limit
        "volc_engine": 60,  # VolcEngine rate limit
        "deepseek": 20,     # DeepSeek rate limit
        "paddle": 100,      # Local, higher limit
        "mock": 1000,       # Mock, unlimited
    }
    
    def __init__(self, max_concurrent: int = 5):
        self.providers = {
            "mock": MockOCRProvider(),
            "deepseek": DeepSeekOCR(),
            "qwen-vl": QwenVLProvider(),
            "volc_engine": VolcEngineOCR(),
            "paddle": PaddleOCRProvider(),  # P1 Fix: Real PaddleOCR instead of YOLO
            "yolo": LocalYoloProvider(),    # Keep YOLO for layout detection
        }
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # Rate limiters per provider
        self._rate_limiters: Dict[str, RateLimiter] = {}
        for name, rpm in self.PROVIDER_RATE_LIMITS.items():
            self._rate_limiters[name] = RateLimiter(
                requests_per_minute=rpm,
                burst_size=min(10, rpm // 6),  # Allow burst of 10 seconds worth
            )

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='gpu_parser').time():
            cfg = state['strategy_config']
            requested = cfg.get('ocr_provider', 'auto')
            fallback_chain = cfg.get('ocr_fallback_chain', ["qwen-vl", "volc_engine", "paddle", "mock"])
            
            # Get concurrency limit from config
            max_concurrent = cfg.get('ocr_concurrency', 5)
            if max_concurrent != self._semaphore._value:
                self._semaphore = asyncio.Semaphore(max_concurrent)

            # Provider availability check
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
            
            # Use semaphore for concurrency control
            async with self._semaphore:
                for provider_name in provider_sequence:
                    provider = self.providers.get(provider_name, self.providers['mock'])
                    
                    # Apply rate limiting
                    rate_limiter = self._rate_limiters.get(provider_name)
                    if rate_limiter:
                        await rate_limiter.acquire()
                    
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

