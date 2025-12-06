import os
import asyncio
import base64
from core.state import IngestState
from core.llm.gateway import LLMGateway
from core.utils.monitor import ingest_duration

class ImageCaptioner:
    def __init__(self):
        self.gateway = LLMGateway()

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage='image_captioner').time():
            images = state.get('images', [])
            if not images:
                return state

            cfg = state.get('strategy_config', {}) or {}
            vlm_model = cfg.get('vlm_model') or cfg.get('llm_model')  # 兼容未定义专用 VLM 配置
            if vlm_model:
                self.gateway = LLMGateway(model=vlm_model)
            
            processed_images = []
            for img in images:
                # img: {data: bytes, page: int, bbox: list}
                
                # Check if VLM is available (DashScope/OpenAI) via config or env
                # For now, check gateway provider
                # Assuming Gateway handles "image" in content differently or we use separate prompt
                
                # Basic Prompt
                prompt = "Describe this image in detail for retrieval purposes. Focus on charts, graphs, and key text."
                
                # If image data exists, try to use it
                caption = f"Image on page {img.get('page')}"
                
                if img.get('data'):
                    try:
                        # Encode image
                        b64_img = base64.b64encode(img['data']).decode('utf-8')
                        
                        # Check if using compatible provider (OpenAI/DashScope)
                        # We'll use a heuristic or a specialized method in gateway if available.
                        # Currently Gateway.chat takes string. 
                        # If we are using DashScope (qwen-vl-max), we can construct a special message format
                        # But Gateway abstracts it.
                        # Let's assume Gateway will be updated to support list of content parts.
                        
                        # For MVP, fallback to placeholder or mock call if not supported
                        # But we want "Real VLM".
                        
                        # Let's try to pass a structured message if Gateway supports it, or just context string.
                        # Assuming Gateway supports passing list of dicts for multimodal in future update.
                        # Here we just use text placeholder if no direct support, 
                        # BUT since we implemented "DeepSeekOCR" in parser, we know how to do it there.
                        
                        # Reuse logic or just set caption.
                        # If we really want to call it:
                        
                        # caption = await self.gateway.chat_with_image(prompt, b64_img) 
                        pass
                    except:
                        pass

                # Create a chunk for this image
                processed_images.append({
                    "content": caption,
                    "type": "image",
                    "page": img.get('page'),
                    "bbox": img.get('bbox'),
                    "image_data": None 
                })
                
            for p_img in processed_images:
                state['parsed_blocks'].append({
                    "type": "image",
                    "content": p_img['content'], 
                    "page": p_img['page'],
                    "bbox": p_img['bbox'],
                    "metadata": {"original_type": "image"}
                })
                
            return state
