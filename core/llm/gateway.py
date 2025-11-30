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
