import asyncio
import json
import os
import time
import uuid
import logging
from typing import Literal

from sqlalchemy.future import select

from core.utils.trace import set_span_attrs
from server.config import settings
from server.database import AsyncSessionLocal
from server.models import ModelConfig, Provider

logger = logging.getLogger(__name__)

# 路由策略类型
RoutingStrategy = Literal["default", "cost_first", "performance_first", "balanced"]


class LLMGateway:
    """
    DB 驱动的 LLM 网关：统一模型选取、熔断/降级、用量记录。
    
    Phase 1 增强：
    - 路由策略支持 (cost_first, performance_first, balanced)
    - 成本追踪集成
    - 预算检查
    - 增强的故障转移
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        # Phase 1 新增参数
        routing_strategy: RoutingStrategy = "default",
        channel_id: str | None = None,
        user_id: str | None = None,
        enable_cost_tracking: bool = True,
    ):
        # 优先使用参数，其次 settings 默认值
        self.default_provider_name = provider or settings.llm_provider or "openai"
        self.default_model_name = model
        self.http_timeout = float(os.environ.get("LLM_HTTP_TIMEOUT", "60"))
        self._cb_state: dict[str, list[float]] = {}  # provider -> list of fail timestamps
        self._cb_cooldown: dict[str, float] = {}  # provider -> next allow timestamp
        # 按模型降级链（可由上层注入）
        self.fallback_models: list[str] = []
        
        # Phase 1 新增属性
        self.routing_strategy = routing_strategy
        self.channel_id = channel_id
        self.user_id = user_id
        self.enable_cost_tracking = enable_cost_tracking
        self._cost_tracker = None
        self._cost_estimator = None
        
        # 故障转移链配置
        self.failover_chain: list[tuple[str, str]] = []  # [(provider, model), ...]

    @property
    def cost_tracker(self):
        """延迟加载 CostTracker"""
        if self._cost_tracker is None:
            from core.llm.cost_tracker import get_cost_tracker
            self._cost_tracker = get_cost_tracker()
        return self._cost_tracker

    @property
    def cost_estimator(self):
        """延迟加载 CostEstimator"""
        if self._cost_estimator is None:
            from core.llm.cost_estimator import get_cost_estimator
            self._cost_estimator = get_cost_estimator()
        return self._cost_estimator

    async def _get_model_config(
        self, provider_name: str, model_name: str | None
    ) -> tuple[Provider | None, ModelConfig | None]:
        """从数据库加载模型配置，优先模型 ID 直查，其次 provider+default"""
        async with AsyncSessionLocal() as session:
            # 先按模型 ID 直接查（避免 provider 名大小写不一致导致 miss）
            if model_name:
                res = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.model_id == model_name, ModelConfig.is_active == True
                    )
                )
                model = res.scalars().first()
                if model:
                    res_prov = await session.execute(
                        select(Provider).where(
                            Provider.id == model.provider_id, Provider.is_active == True
                        )
                    )
                    provider = res_prov.scalars().first()
                    return provider, model

            # 再按 provider 兜底
            res = await session.execute(
                select(Provider).where(
                    Provider.name.ilike(provider_name), Provider.is_active == True
                )
            )
            provider = res.scalars().first()
            if not provider:
                return None, None

            # 查找指定模型或默认模型
            if model_name:
                res = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.provider_id == provider.id,
                        ModelConfig.model_id == model_name,
                        ModelConfig.is_active == True,
                    )
                )
                model = res.scalars().first()
            else:
                res = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.provider_id == provider.id,
                        ModelConfig.is_default == True,
                        ModelConfig.is_active == True,
                    )
                )
                model = res.scalars().first()
            return provider, model

    async def _select_provider(
        self, task_type: str = "chat"
    ) -> tuple[Provider | None, ModelConfig | None]:
        """
        根据路由策略选择 Provider
        Phase 1 新增方法
        """
        if self.routing_strategy == "cost_first":
            return await self._select_cheapest_provider(task_type)
        elif self.routing_strategy == "performance_first":
            return await self._select_fastest_provider(task_type)
        elif self.routing_strategy == "balanced":
            return await self._select_balanced_provider(task_type)
        else:
            # default: 使用配置的 provider/model
            return await self._get_model_config(
                self.default_provider_name,
                self.default_model_name
            )

    async def _select_cheapest_provider(
        self, task_type: str = "chat"
    ) -> tuple[Provider | None, ModelConfig | None]:
        """选择成本最低的 Provider"""
        provider_id, model_id, _ = self.cost_estimator.get_cheapest_provider(
            task_type=task_type,
            require_domestic=True  # 默认优先国内
        )
        return await self._get_model_config(provider_id, model_id)

    async def _select_fastest_provider(
        self, task_type: str = "chat"
    ) -> tuple[Provider | None, ModelConfig | None]:
        """选择性能最优的 Provider（按优先级）"""
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(Provider).where(
                    Provider.is_active == True,
                    Provider.is_healthy == True,
                    Provider.category == "llm"
                ).order_by(Provider.priority.asc())
            )
            provider = res.scalars().first()
            if not provider:
                return None, None
            
            res = await session.execute(
                select(ModelConfig).where(
                    ModelConfig.provider_id == provider.id,
                    ModelConfig.is_active == True,
                    ModelConfig.is_default == True
                )
            )
            model = res.scalars().first()
            return provider, model

    async def _select_balanced_provider(
        self, task_type: str = "chat"
    ) -> tuple[Provider | None, ModelConfig | None]:
        """平衡选择 Provider（考虑成本和性能）"""
        # 获取按成本排序的 providers
        providers_by_cost = self.cost_estimator.get_providers_by_cost(task_type=task_type)
        
        # 选择成本前 3 中优先级最高的
        for provider_id, model_id, _ in providers_by_cost[:3]:
            prov, mdl = await self._get_model_config(provider_id, model_id)
            if prov and mdl and self._cb_allowed(prov.name):
                return prov, mdl
        
        # 回退到默认
        return await self._get_model_config(
            self.default_provider_name,
            self.default_model_name
        )

    async def _check_budget(self) -> tuple[bool, float]:
        """
        检查预算是否允许调用
        Phase 1 新增方法
        
        Returns:
            tuple[bool, float]: (是否允许, 剩余预算)
        """
        if not self.enable_cost_tracking:
            return True, 100.0
        
        return await self.cost_tracker.check_budget(
            channel_id=self.channel_id,
            user_id=self.user_id
        )

    def _usage_dir(self) -> str:
        base = getattr(settings, "usage_dir_resolved", os.path.join(os.getcwd(), "data", "usage"))
        os.makedirs(base, exist_ok=True)
        return base

    def _record_usage(self, kind, provider, model, tokens_in, tokens_out, duration_ms):
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

    def _calculate_cost(
        self,
        provider: Provider,
        model: ModelConfig,
        input_tokens: int,
        output_tokens: int,
        image_count: int = 0
    ) -> float:
        """计算 API 调用成本"""
        return self.cost_estimator.estimate(
            provider_id=provider.name,
            model_id=model.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count
        )

    async def _track_cost(
        self,
        provider: Provider,
        model: ModelConfig,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        success: bool,
        error_message: str | None = None,
        image_count: int = 0
    ):
        """记录成本到数据库 (Phase 1 新增)"""
        if not self.enable_cost_tracking:
            return
        
        from core.llm.cost_tracker import CostRecord
        
        cost_usd = self._calculate_cost(
            provider, model, input_tokens, output_tokens, image_count
        )
        
        record = CostRecord(
            request_id=str(uuid.uuid4()),
            provider_id=provider.name,
            model_id=model.model_id,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
            cached=False,
            error_message=error_message,
            channel_id=self.channel_id,
            user_id=self.user_id,
        )
        
        await self.cost_tracker.track(record)


    async def chat(self, prompt: str, context: str | None = None) -> str:
        """
        Chat API 调用
        
        Phase 1 增强：
        - 预算检查
        - 路由策略
        - 成本追踪
        - 增强的故障转移
        """
        t0 = time.perf_counter()

        # Phase 1: 预算检查
        allowed, remaining = await self._check_budget()
        if not allowed:
            from core.llm.exceptions import BudgetExceededError
            raise BudgetExceededError(
                f"Budget exceeded for channel: {self.channel_id}",
                scope="channel" if self.channel_id else "global",
                remaining=remaining
            )

        # Phase 1: 使用路由策略选择 Provider
        prov, mdl = await self._select_provider("chat")

        # 若主模型缺失，尝试降级链
        if not prov or not mdl:
            for mid in self.fallback_models:
                prov_f, mdl_f = await self._get_model_config(self.default_provider_name, mid)
                if prov_f and mdl_f:
                    prov, mdl = prov_f, mdl_f
                    break

        # Phase 1: 尝试 failover_chain
        if not prov or not mdl:
            for fp, fm in self.failover_chain:
                prov_f, mdl_f = await self._get_model_config(fp, fm)
                if prov_f and mdl_f and self._cb_allowed(prov_f.name):
                    prov, mdl = prov_f, mdl_f
                    logger.info(f"Failover to {fp}/{fm}")
                    break

        # 未找到任何可用模型，显式报错
        if not prov or not mdl:
            from core.llm.exceptions import ProviderUnavailableError
            err_msg = "No active LLM model found in DB (provider/model missing)."
            set_span_attrs({"llm.error": err_msg})
            raise ProviderUnavailableError(err_msg, tried_providers=[self.default_provider_name])

        # Use DB Config
        import httpx

        api_key = prov.api_key
        base_url = prov.base_url
        model_id = mdl.model_id
        if not base_url:
            raise RuntimeError(f"LLM provider `{prov.name}` missing base_url")
        if not model_id:
            raise RuntimeError(f"LLM model config missing model_id for provider `{prov.name}`")

        # OpenAI-compatible generic handler
        if prov.category == "llm":
            content = prompt if not context else f"{prompt}\n\nContext:\n{context}"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

            # Construct request
            url = f"{base_url.rstrip('/')}/chat/completions"
            # Handle DashScope compat URL quirk if base_url is raw
            if "dashscope" in base_url and "compatible-mode" not in base_url:
                url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

            body = {
                "model": model_id,
                "messages": [{"role": "user", "content": content}],
                "stream": False,
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

            input_tokens = len(content) // 4
            output_tokens = 0
            
            try:
                out = await asyncio.to_thread(self._http_retry, _req)
                dur = int((time.perf_counter() - t0) * 1000)
                output_tokens = len(out) // 4
                
                # 原有用量记录
                self._record_usage(
                    "chat", prov.name, model_id, input_tokens, output_tokens, dur
                )
                
                # Phase 1: 成本追踪
                await self._track_cost(
                    provider=prov,
                    model=mdl,
                    task_type="chat",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=dur,
                    success=True
                )
                
                self._cb_on_success(prov.name)
                return out
            except Exception as e:
                dur = int((time.perf_counter() - t0) * 1000)
                self._cb_on_fail(prov.name)
                
                # Phase 1: 记录失败的成本
                await self._track_cost(
                    provider=prov,
                    model=mdl,
                    task_type="chat",
                    input_tokens=input_tokens,
                    output_tokens=0,
                    latency_ms=dur,
                    success=False,
                    error_message=str(e)
                )
                
                set_span_attrs({"llm.error": str(e), "llm.provider": prov.name})
                
                # Phase 1: 尝试 failover
                for fp, fm in self.failover_chain:
                    if fp == prov.name:
                        continue
                    try:
                        prov_f, mdl_f = await self._get_model_config(fp, fm)
                        if prov_f and mdl_f and self._cb_allowed(prov_f.name):
                            logger.info(f"Failover from {prov.name} to {fp}/{fm}")
                            # 递归调用，但使用新的 provider
                            old_provider = self.default_provider_name
                            old_model = self.default_model_name
                            self.default_provider_name = fp
                            self.default_model_name = fm
                            self.routing_strategy = "default"  # 避免再次路由
                            try:
                                return await self.chat(prompt, context)
                            finally:
                                self.default_provider_name = old_provider
                                self.default_model_name = old_model
                    except Exception:
                        continue
                
                raise

        # 未支持的类别明确报错
        raise RuntimeError(f"Unsupported provider category: {prov.category}")

    async def health_check(self, provider: str | None = None, model: str | None = None) -> bool:
        """简单健康检查：尝试从 DB 读取配置并返回存在性"""
        prov, mdl = await self._get_model_config(
            provider or self.default_provider_name, model or self.default_model_name
        )
        return bool(prov and mdl)

    async def get_cost_summary(self) -> dict:
        """获取成本汇总 (Phase 1 新增)"""
        return await self.cost_tracker.get_cost_summary(channel_id=self.channel_id)
