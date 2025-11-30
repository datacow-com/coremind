from typing import Optional
import os


class LLMGateway:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
        self.model = model

    async def chat(self, prompt: str, context: Optional[str] = None) -> str:
        p = self.provider.lower()
        if p == "openai" and os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                oa = OpenAI()
                mdl = self.model or os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
                content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
                resp = oa.chat.completions.create(
                    model=mdl,
                    messages=[{"role": "user", "content": content}],
                    temperature=float(os.environ.get("CHAT_TEMPERATURE", "0.2")),
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception:
                pass
        if p == "gemini" and os.environ.get("GEMINI_API_KEY"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=os.environ["GEMINI_API_KEY"])
                mdl = self.model or os.environ.get("GEMINI_CHAT_MODEL", "gemini-1.5-flash")
                content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
                model = genai.GenerativeModel(mdl)
                resp = model.generate_content(content)
                return getattr(resp, "text", "").strip()
            except Exception:
                pass
        if p == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
            try:
                import httpx
                mdl = self.model or os.environ.get("OPENROUTER_CHAT_MODEL", "meta-llama/llama-3.1-8b-instruct")
                content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
                headers = {
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": mdl,
                    "messages": [{"role": "user", "content": content}],
                }
                with httpx.Client(timeout=20.0) as http:
                    r = http.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                    if r.status_code == 200:
                        data = r.json()
                        return (data["choices"][0]["message"]["content"] or "").strip()
            except Exception:
                pass
        # fallback
        return ""

    async def stream_chat(self, prompt: str, context: Optional[str] = None):
        p = self.provider.lower()
        if p == "openai" and os.environ.get("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                oa = OpenAI()
                mdl = self.model or os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")
                content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
                stream = oa.chat.completions.create(
                    model=mdl,
                    messages=[{"role": "user", "content": content}],
                    temperature=float(os.environ.get("CHAT_TEMPERATURE", "0.2")),
                    stream=True,
                )
                for ev in stream:
                    try:
                        delta = ev.choices[0].delta.content
                        if delta:
                            yield delta
                    except Exception:
                        continue
                return
            except Exception:
                pass
        if p == "gemini" and os.environ.get("GEMINI_API_KEY"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=os.environ["GEMINI_API_KEY"])
                mdl = self.model or os.environ.get("GEMINI_CHAT_MODEL", "gemini-1.5-flash")
                content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
                model = genai.GenerativeModel(mdl)
                resp = model.generate_content(content, stream=True)
                for ch in resp:
                    txt = getattr(ch, "text", "")
                    if txt:
                        yield txt
                return
            except Exception:
                pass
        # fallback: yield final answer once
        ans = await self.chat(prompt=prompt, context=context)
        if ans:
            yield ans

    async def vision_markdown(self, image_bytes: bytes, prompt: str, model: Optional[str] = None) -> str:
        p = self.provider
        # DashScope (Qwen-VL compatible-mode)
        if p == "dashscope" and os.environ.get("DASHSCOPE_API_KEY"):
            import base64
            import httpx
            key = os.environ.get("DASHSCOPE_API_KEY")
            url = os.environ.get("DASHSCOPE_COMPAT_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
            mdl = model or self.model or os.environ.get("DASHSCOPE_VISION_MODEL", "qwen-plus")
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            body = {
                "model": mdl,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
                        ],
                    }
                ],
                "stream": False,
                "max_tokens": int(os.environ.get("VISION_MAX_TOKENS", "2000")),
            }
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    data = r.json()
                    return (
                        ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    ).strip()
            except Exception:
                return ""
        # Volcengine Ark (compatible-mode)
        if p in {"ark", "volcengine"} and os.environ.get("VOLCENGINE_API_KEY"):
            import base64
            import httpx
            key = os.environ.get("VOLCENGINE_API_KEY")
            url = os.environ.get("VOLCENGINE_COMPAT_URL", "https://api.ark.cn-beijing.volces.com/v3/chat/completions")
            mdl = model or self.model or os.environ.get("VOLCENGINE_VISION_MODEL", os.environ.get("ARK_VISION_MODEL", "ep-vision"))
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            body = {
                "model": mdl,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"},
                        ],
                    }
                ],
                "stream": False,
                "max_tokens": int(os.environ.get("VISION_MAX_TOKENS", "2000")),
            }
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    r = await client.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    data = r.json()
                    return (
                        ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    ).strip()
            except Exception:
                return ""
        # Gemini vision (fallback if explicitly set)
        if p == "gemini" and os.environ.get("GEMINI_API_KEY"):
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            try:
                mdl = model or self.model or os.environ.get("GEMINI_VISION_MODEL", "gemini-1.5-flash")
                gg = genai.GenerativeModel(mdl)
                resp = gg.generate_content([
                    {"role": "user", "parts": [
                        prompt,
                        {"mime_type": "image/png", "data": image_bytes},
                    ]}
                ])
                return getattr(resp, "text", "").strip()
            except Exception:
                return ""
        return ""

    async def vision_table_markdown(self, image_bytes: bytes, model: Optional[str] = None) -> str:
        prompt = "将此表格图片转换为Markdown表格，确保数值精确，保留合并单元格结构。"
        return await self.vision_markdown(image_bytes=image_bytes, prompt=prompt, model=model)
