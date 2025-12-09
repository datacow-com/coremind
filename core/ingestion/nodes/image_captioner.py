"""
Image Captioner Node - Generates descriptions for images using VLM.

Supports multiple VLM providers:
- DashScope (Qwen-VL)
- OpenAI (GPT-4V)
- DeepSeek (Janus)
"""

import asyncio
import base64
import os
from typing import Any

import httpx

from core.state import IngestState
from core.utils.monitor import ingest_duration


class ImageCaptioner:
    """Generates image captions using Vision Language Models."""

    def __init__(self):
        self.timeout = float(os.environ.get("VLM_TIMEOUT", "30"))
        self._semaphore = asyncio.Semaphore(3)  # Limit concurrent VLM calls

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage="image_captioner").time():
            images = state.get("images", [])
            if not images:
                return state

            cfg = state.get("strategy_config", {}) or {}
            vlm_provider = cfg.get("vlm_provider") or cfg.get("ocr_provider") or "auto"
            vlm_model = cfg.get("vlm_model")

            # Process images concurrently with semaphore
            tasks = [self._caption_image(img, vlm_provider, vlm_model) for img in images]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Add captions to parsed_blocks
            for img, result in zip(images, results, strict=False):
                if isinstance(result, Exception):
                    caption = f"[Image on page {img.get('page')}]"
                    state["error_log"].append(
                        {
                            "stage": "image_captioner",
                            "error": str(result),
                            "page": img.get("page"),
                        }
                    )
                else:
                    caption = result

                state["parsed_blocks"].append(
                    {
                        "type": "image",
                        "content": caption,
                        "page": img.get("page"),
                        "bbox": img.get("bbox"),
                        "metadata": {"original_type": "image", "vlm_provider": vlm_provider},
                    }
                )

            return state

    async def _caption_image(self, img: dict[str, Any], provider: str, model: str | None) -> str:
        """Generate caption for a single image."""
        async with self._semaphore:
            image_data = img.get("data")
            if not image_data:
                return f"[Image on page {img.get('page')}]"

            b64_img = base64.b64encode(image_data).decode("utf-8")
            prompt = (
                "Describe this image in detail for document retrieval. "
                "Focus on: 1) Charts/graphs: describe data trends and values. "
                "2) Tables: describe structure and key data. "
                "3) Diagrams: describe components and relationships. "
                "4) Text: transcribe visible text. "
                "Be concise but comprehensive."
            )

            # Try providers in order
            if provider == "auto":
                providers = ["dashscope", "openai", "deepseek"]
            else:
                providers = [provider]

            for prov in providers:
                try:
                    if prov == "dashscope" and os.environ.get("DASHSCOPE_API_KEY"):
                        return await self._call_dashscope(prompt, b64_img, model)
                    elif prov == "openai" and os.environ.get("OPENAI_API_KEY"):
                        return await self._call_openai(prompt, b64_img, model)
                    elif prov == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
                        return await self._call_deepseek(prompt, b64_img, model)
                except Exception:
                    continue

            # Fallback
            return f"[Image on page {img.get('page')}]"

    async def _call_dashscope(self, prompt: str, b64_img: str, model: str | None) -> str:
        """Call DashScope Qwen-VL API."""
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        model_id = model or "qwen-vl-max"

        # Determine image format from base64 header or default to jpeg
        mime_type = "image/jpeg"
        if b64_img.startswith("/9j/"):
            mime_type = "image/jpeg"
        elif b64_img.startswith("iVBOR"):
            mime_type = "image/png"

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64_img}"},
                        },
                    ],
                }
            ],
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_openai(self, prompt: str, b64_img: str, model: str | None) -> str:
        """Call OpenAI GPT-4V API."""
        api_key = os.environ.get("OPENAI_API_KEY")
        model_id = model or "gpt-4o-mini"

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                        },
                    ],
                }
            ],
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_deepseek(self, prompt: str, b64_img: str, model: str | None) -> str:
        """Call DeepSeek Janus API."""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model_id = model or "deepseek-vl"

        url = f"{base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"},
                        },
                    ],
                }
            ],
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
