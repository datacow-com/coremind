from typing import Optional
import os


class LLMGateway:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
        self.model = model

    def _usage_dir(self) -> str:
        base = os.path.join(os.getcwd(), "data", "usage")
        os.makedirs(base, exist_ok=True)
        return base

    def _record_usage(self, kind: str, provider: str, model: str, tokens_in: int, tokens_out: int, duration_ms: int) -> None:
        import json, time, httpx
        path = os.path.join(self._usage_dir(), "usage.jsonl")
        rec = {
            "ts": int(time.time()),
            "kind": kind,
            "provider": provider,
            "model": model,
            "tokens_in": int(tokens_in or 0),
            "tokens_out": int(tokens_out or 0),
            "duration_ms": int(duration_ms or 0),
        }
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # Threshold check and webhook
        try:
            th_path = os.path.join(self._usage_dir(), "thresholds.json")
            if os.path.exists(th_path):
                with open(th_path, "r", encoding="utf-8") as tf:
                    th = json.load(tf)
                # Simple daily aggregation in-memory
                day = time.strftime("%Y-%m-%d", time.gmtime(rec["ts"]))
                agg_tokens = 0
                agg_calls = 0
                try:
                    with open(path, "r", encoding="utf-8") as rf:
                        for line in rf:
                            try:
                                x = json.loads(line.strip())
                                d = time.strftime("%Y-%m-%d", time.gmtime(x.get("ts", rec["ts"])))
                                if d == day:
                                    agg_calls += 1
                                    agg_tokens += int(x.get("tokens_in") or 0) + int(x.get("tokens_out") or 0)
                            except Exception:
                                continue
                except Exception:
                    pass
                exceed = (
                    (int(th.get("max_tokens_per_day") or 0) and agg_tokens >= int(th.get("max_tokens_per_day") or 0))
                    or (int(th.get("max_calls_per_day") or 0) and agg_calls >= int(th.get("max_calls_per_day") or 0))
                )
                webhook = th.get("webhook_url")
                if exceed and webhook:
                    payload = {
                        "day": day,
                        "calls": agg_calls,
                        "tokens": agg_tokens,
                        "provider": provider,
                        "model": model,
                        "kind": kind,
                        "msg": "Threshold exceeded",
                    }
                    try:
                        with httpx.Client(timeout=5.0) as http:
                            http.post(webhook, json=payload)
                    except Exception:
                        pass

    async def chat(self, prompt: str, context: Optional[str] = None) -> str:
        import time
        t0 = time.perf_counter()
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
                out = (resp.choices[0].message.content or "").strip()
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("chat", p, mdl, len(content) // 4, len(out) // 4, dur)
                return out
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
                out = getattr(resp, "text", "").strip()
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("chat", p, mdl, len(content) // 4, len(out) // 4, dur)
                return out
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
                        out = (data["choices"][0]["message"]["content"] or "").strip()
                        dur = int((time.perf_counter() - t0) * 1000)
                        self._record_usage("chat", p, mdl, len(content) // 4, len(out) // 4, dur)
                        return out
            except Exception:
                pass
        # fallback
        return ""

    async def stream_chat(self, prompt: str, context: Optional[str] = None):
        import time
        t0 = time.perf_counter()
        p = self.provider.lower()
        acc = []
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
                            acc.append(delta)
                            yield delta
                    except Exception:
                        continue
                out = "".join(acc)
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("chat_stream", p, mdl, len(content) // 4, len(out) // 4, dur)
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
                        acc.append(txt)
                        yield txt
                out = "".join(acc)
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("chat_stream", p, mdl, len(content) // 4, len(out) // 4, dur)
                return
            except Exception:
                pass
        # fallback: yield final answer once
        ans = await self.chat(prompt=prompt, context=context)
        if ans:
            dur = int((time.perf_counter() - t0) * 1000)
            self._record_usage("chat_stream", p, self.model or "", len(prompt) // 4, len(ans) // 4, dur)
            yield ans

    async def vision_markdown(self, image_bytes: bytes, prompt: str, model: Optional[str] = None) -> str:
        import time
        t0 = time.perf_counter()
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
                    out = (
                        ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    ).strip()
                    dur = int((time.perf_counter() - t0) * 1000)
                    self._record_usage("vision", p, mdl, len(prompt) // 4, len(out) // 4, dur)
                    return out
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
                    out = (
                        ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                    ).strip()
                    dur = int((time.perf_counter() - t0) * 1000)
                    self._record_usage("vision", p, mdl, len(prompt) // 4, len(out) // 4, dur)
                    return out
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
                out = getattr(resp, "text", "").strip()
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("vision", p, (model or self.model or "gemini-1.5-flash"), len(prompt) // 4, len(out) // 4, dur)
                return out
            except Exception:
                return ""
        return ""

    async def vision_table_markdown(self, image_bytes: bytes, model: Optional[str] = None) -> str:
        prompt = "将此表格图片转换为Markdown表格，确保数值精确，保留合并单元格结构。"
        return await self.vision_markdown(image_bytes=image_bytes, prompt=prompt, model=model)
