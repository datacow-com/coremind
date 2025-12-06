import json
import os
import time
import asyncio
from typing import Optional, Tuple, List
from sqlalchemy.future import select
from server.database import AsyncSessionLocal
from server.models import Provider, ModelConfig
from server.config import settings
from core.utils.trace import set_span_attrs

class LLMGateway:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        # 优先使用参数，其次 settings 默认值
        self.default_provider_name = provider or settings.llm_provider or "openai"
        self.default_model_name = model
        self.http_timeout = float(os.environ.get("LLM_HTTP_TIMEOUT", "60"))
        self._cb_state: dict[str, list[float]] = {}  # provider -> list of fail timestamps
        self._cb_cooldown: dict[str, float] = {}  # provider -> next allow timestamp
        # 按模型降级链（可由上层注入）
        self.fallback_models: List[str] = []

    async def _get_model_config(self, provider_name: str, model_name: Optional[str]) -> Tuple[Optional[Provider], Optional[ModelConfig]]:
        """从数据库加载模型配置，优先模型 ID 直查，其次 provider+default"""
        async with AsyncSessionLocal() as session:
            # 先按模型 ID 直接查（避免 provider 名大小写不一致导致 miss）
            if model_name:
                res = await session.execute(select(ModelConfig).where(
                    ModelConfig.model_id == model_name,
                    ModelConfig.is_active == True
                ))
                model = res.scalars().first()
                if model:
                    res_prov = await session.execute(select(Provider).where(
                        Provider.id == model.provider_id,
                        Provider.is_active == True
                    ))
                    provider = res_prov.scalars().first()
                    return provider, model

            # 再按 provider 兜底
            res = await session.execute(select(Provider).where(
                Provider.name.ilike(provider_name),
                Provider.is_active == True
            ))
            provider = res.scalars().first()
            if not provider:
                return None, None
            
            # 查找指定模型或默认模型
            if model_name:
                res = await session.execute(select(ModelConfig).where(
                    ModelConfig.provider_id == provider.id, 
                    ModelConfig.model_id == model_name,
                    ModelConfig.is_active == True
                ))
                model = res.scalars().first()
            else:
                res = await session.execute(select(ModelConfig).where(
                    ModelConfig.provider_id == provider.id, 
                    ModelConfig.is_default == True,
                    ModelConfig.is_active == True
                ))
                model = res.scalars().first()
            return provider, model

    # ... (保留 _usage_dir, _record_usage, _cb_allowed, _cb_on_fail, _cb_on_success, _http_retry 方法) ...
    
    def _usage_dir(self) -> str:
        base = getattr(settings, "usage_dir_resolved", os.path.join(os.getcwd(), "data", "usage"))
        os.makedirs(base, exist_ok=True)
        return base

    def _record_usage(self, kind, provider, model, tokens_in, tokens_out, duration_ms):
        import json
        import time
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

    def _cb_allowed(self, provider: str) -> bool:
        now = time.time()
        next_allow = self._cb_cooldown.get(provider)
        if next_allow and now < next_allow:
            return False
        return True

    def _cb_on_fail(self, provider: str) -> None:
        now = time.time()
        window = 60.0
        max_fail = 3
        fails = [t for t in self._cb_state.get(provider, []) if now - t <= window]
        fails.append(now)
        self._cb_state[provider] = fails
        if len(fails) >= max_fail:
            self._cb_cooldown[provider] = now + 30.0

    def _cb_on_success(self, provider: str) -> None:
        self._cb_state.pop(provider, None)
        self._cb_cooldown.pop(provider, None)

    def _http_retry(self, fn, attempts: int = 2, backoff_ms: int = 500):
        last_err = None
        for i in range(attempts + 1):
            try:
                return fn()
            except Exception as err:
                last_err = err
                if i >= attempts:
                    break
                time.sleep((backoff_ms * (2**i)) / 1000)
        if last_err:
            raise last_err

    async def chat(self, prompt: str, context: Optional[str] = None) -> str:
        t0 = time.perf_counter()
        
        # Load config from DB
        prov, mdl = await self._get_model_config(self.default_provider_name, self.default_model_name)

        # 若主模型缺失，尝试降级链
        if not prov or not mdl:
            for mid in self.fallback_models:
                prov_f, mdl_f = await self._get_model_config(self.default_provider_name, mid)
                if prov_f and mdl_f:
                    prov, mdl = prov_f, mdl_f
                    break

        # 未找到任何可用模型，显式报错，避免沉默
        if not prov or not mdl:
            err_msg = "No active LLM model found in DB (provider/model missing)."
            set_span_attrs({"llm.error": err_msg})
            raise RuntimeError(err_msg)

        # Use DB Config
        import httpx
        
        api_key = prov.api_key
        base_url = prov.base_url
        model_id = mdl.model_id
        
        # OpenAI-compatible generic handler
        if prov.category == 'llm':
            content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Adjust headers/url for specific providers if needed based on provider name
            if prov.name.lower() == 'dashscope':
                # DashScope specific
                pass # Usually compatible if using compat url
            
            # Construct request
            url = f"{base_url.rstrip('/')}/chat/completions"
            # Handle DashScope compat URL quirk if base_url is raw
            if "dashscope" in base_url and "compatible-mode" not in base_url:
                 url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

            body = {
                "model": model_id,
                "messages": [{"role": "user", "content": content}],
                "stream": False
            }
            
            # Merge parameters
            if mdl and mdl.parameters:
                body.update(mdl.parameters)

            def _req():
                if not self._cb_allowed(prov.name):
                    raise RuntimeError("circuit open")
                with httpx.Client(timeout=self.http_timeout) as http:
                    r = http.post(url, headers=headers, json=body)
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"].strip()

            try:
                out = await asyncio.to_thread(self._http_retry, _req)
                dur = int((time.perf_counter() - t0) * 1000)
                self._record_usage("chat", prov.name, model_id, len(content)//4, len(out)//4, dur)
                self._cb_on_success(prov.name)
                return out
            except Exception as e:
                self._cb_on_fail(prov.name)
                set_span_attrs({"llm.error": str(e), "llm.provider": prov.name})
                raise
                
        return ""

    async def health_check(self, provider: Optional[str] = None, model: Optional[str] = None) -> bool:
        """简单健康检查：尝试从 DB 读取配置并返回存在性"""
        prov, mdl = await self._get_model_config(provider or self.default_provider_name, model or self.default_model_name)
        return bool(prov and mdl)
