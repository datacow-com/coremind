"""
Base Domain Interpreter - 领域解读器基类

Phase 2: 垂直领域增强
提供统一的领域解读接口，集成 Phase 1 LLM Gateway。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import logging
import time

from core.domains.ontology_schema import OntologySchema
from core.domains.exceptions import DomainInterpretationError

logger = logging.getLogger(__name__)


@dataclass
class InterpretationResult:
    """领域解读结果"""
    domain_id: str
    structured_data: dict[str, Any]
    narrative: str
    confidence: float  # 0.0 - 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_elements: list[dict] = field(default_factory=list)

    def __post_init__(self):
        """验证字段"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be between 0 and 1, got {self.confidence}")
        if not self.domain_id:
            raise ValueError("domain_id cannot be empty")


class BaseDomainInterpreter(ABC):
    """
    领域解读器基类
    
    所有垂直领域解读器必须继承此类并实现抽象方法。
    """

    # 子类必须定义
    domain_id: str = ""
    requires_gpu: bool = False
    recommended_vram_mb: int = 0

    def __init__(self):
        self._gateway = None
        self._cost_tracker = None
        self._cost_estimator = None
        self._gpu_available: bool | None = None

    @property
    def gateway(self):
        """延迟加载 LLMGateway"""
        if self._gateway is None:
            from core.llm.gateway import LLMGateway
            self._gateway = LLMGateway(
                enable_cost_tracking=True,
                routing_strategy="balanced"
            )
        return self._gateway

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

    @abstractmethod
    async def interpret(
        self,
        document: dict,
        config: dict | None = None
    ) -> InterpretationResult:
        """
        解读文档
        
        Args:
            document: 文档数据，包含 content, images, metadata 等
            config: 解读配置
            
        Returns:
            InterpretationResult: 解读结果
        """
        pass

    @abstractmethod
    def get_ontology(self) -> OntologySchema:
        """
        获取领域本体定义
        
        Returns:
            OntologySchema: 本体定义
        """
        pass

    @abstractmethod
    def validate_output(
        self,
        result: InterpretationResult
    ) -> tuple[bool, list[str]]:
        """
        验证解读结果是否符合本体定义
        
        Args:
            result: 解读结果
            
        Returns:
            tuple[bool, list[str]]: (是否有效, 违规列表)
        """
        pass

    def _check_gpu_available(self, force_recheck: bool = False) -> bool:
        """
        检查 GPU 是否可用
        
        Phase 2: GPU 资源管理
        - 检查 CUDA 可用性
        - 验证显存是否满足推荐要求
        - 支持强制重新检查
        
        Args:
            force_recheck: 是否强制重新检查（忽略缓存）
            
        Returns:
            bool: GPU 是否可用且满足要求
        """
        if self._gpu_available is not None and not force_recheck:
            return self._gpu_available

        try:
            import torch
            
            # 检查 CUDA 是否可用
            if not torch.cuda.is_available():
                logger.info("CUDA not available, will use cloud VLM")
                self._gpu_available = False
                return False
            
            # 检查显存是否足够
            device = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(device)
            total_memory_mb = props.total_memory / (1024 * 1024)
            
            # 获取当前可用显存
            free_memory = torch.cuda.mem_get_info(device)[0]
            free_memory_mb = free_memory / (1024 * 1024)
            
            if total_memory_mb < self.recommended_vram_mb:
                logger.warning(
                    f"GPU total memory {total_memory_mb:.0f}MB < recommended {self.recommended_vram_mb}MB, "
                    f"will use cloud VLM"
                )
                self._gpu_available = False
            elif free_memory_mb < self.recommended_vram_mb * 0.8:
                # 可用显存不足推荐值的 80%
                logger.warning(
                    f"GPU free memory {free_memory_mb:.0f}MB < 80% of recommended {self.recommended_vram_mb}MB, "
                    f"will use cloud VLM"
                )
                self._gpu_available = False
            else:
                logger.info(
                    f"GPU available: {props.name}, "
                    f"total={total_memory_mb:.0f}MB, free={free_memory_mb:.0f}MB"
                )
                self._gpu_available = True
                
        except ImportError:
            logger.info("PyTorch not installed, will use cloud VLM")
            self._gpu_available = False
        except Exception as e:
            logger.warning(f"GPU check failed: {e}, will use cloud VLM")
            self._gpu_available = False

        return self._gpu_available
    
    def _should_use_cloud_vlm(self) -> bool:
        """
        判断是否应该使用云端 VLM
        
        Phase 2: GPU 资源管理
        当本地 GPU 不可用或不满足要求时，自动回退到云端
        
        Returns:
            bool: 是否应该使用云端 VLM
        """
        if not self.requires_gpu:
            # 不需要 GPU 的解读器，默认使用云端
            return True
        
        return not self._check_gpu_available()

    async def _call_vlm(
        self,
        image_data: bytes,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        skip_budget_check: bool = False
    ) -> str:
        """
        调用 VLM 进行图像理解
        
        Phase 2: GPU 资源管理和成本集成
        - 支持 GPU 不可用时自动回退到云端
        - 集成成本追踪
        - 调用前检查预算
        
        Args:
            image_data: 图像二进制数据
            prompt: 提示词
            provider: 指定 Provider（可选）
            model: 指定模型（可选）
            skip_budget_check: 是否跳过预算检查
            
        Returns:
            str: VLM 响应文本
        """
        t0 = time.perf_counter()

        # Phase 2: 预算检查
        if not skip_budget_check:
            allowed, remaining = await self._check_budget_before_call(
                task_type="vision",
                estimated_input_tokens=len(prompt) // 4,
                image_count=1
            )
            if not allowed:
                from core.llm.exceptions import BudgetExceededError
                raise BudgetExceededError(
                    f"Budget exceeded, remaining: ${remaining:.4f}",
                    scope="domain",
                    remaining=remaining
                )

        # 检查是否应该使用云端 VLM
        use_local = not self._should_use_cloud_vlm() and not provider

        if use_local:
            # 尝试本地 VLM
            try:
                result = await self._call_local_vlm(image_data, prompt)
                logger.debug(f"Local VLM call took {time.perf_counter() - t0:.2f}s")
                return result
            except NotImplementedError:
                logger.info("Local VLM not implemented, using cloud VLM")
            except Exception as e:
                logger.warning(f"Local VLM failed, falling back to cloud: {e}")

        # 云端 VLM 调用
        return await self._call_cloud_vlm(image_data, prompt, provider, model)

    async def _call_local_vlm(self, image_data: bytes, prompt: str) -> str:
        """调用本地 VLM（子类可覆盖）"""
        raise NotImplementedError("Local VLM not implemented")

    async def _call_cloud_vlm(
        self,
        image_data: bytes,
        prompt: str,
        provider: str | None = None,
        model: str | None = None
    ) -> str:
        """
        调用云端 VLM
        
        使用 Phase 1 Gateway 的 VLM 能力。
        """
        import base64
        import httpx
        import asyncio

        from core.llm.gateway import LLMGateway
        from server.database import AsyncSessionLocal
        from server.models import Provider as ProviderModel, ModelConfig
        from sqlalchemy.future import select

        # 获取 VLM Provider 配置
        async with AsyncSessionLocal() as session:
            if provider:
                res = await session.execute(
                    select(ProviderModel).where(
                        ProviderModel.name.ilike(provider),
                        ProviderModel.is_active == True
                    )
                )
            else:
                # 默认使用 dashscope qwen-vl
                res = await session.execute(
                    select(ProviderModel).where(
                        ProviderModel.name.ilike("dashscope"),
                        ProviderModel.is_active == True
                    )
                )
            prov = res.scalars().first()

            if not prov:
                raise DomainInterpretationError(
                    "No VLM provider available",
                    domain_id=self.domain_id,
                    stage="vlm_call",
                    details={"provider": provider}
                )

            # 获取 VLM 模型
            if model:
                res = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.provider_id == prov.id,
                        ModelConfig.model_id == model,
                        ModelConfig.is_active == True
                    )
                )
            else:
                res = await session.execute(
                    select(ModelConfig).where(
                        ModelConfig.provider_id == prov.id,
                        ModelConfig.model_id.like("%vl%"),
                        ModelConfig.is_active == True
                    )
                )
            mdl = res.scalars().first()

            if not mdl:
                raise DomainInterpretationError(
                    "No VLM model available",
                    domain_id=self.domain_id,
                    stage="vlm_call",
                    details={"provider": prov.name, "model": model}
                )

        # 构建请求
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # OpenAI-compatible vision API
        url = f"{prov.base_url.rstrip('/')}/chat/completions"
        if "dashscope" in prov.base_url and "compatible-mode" not in prov.base_url:
            url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {prov.api_key}",
            "Content-Type": "application/json"
        }

        body = {
            "model": mdl.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "stream": False
        }

        t0 = time.perf_counter()
        input_tokens = len(prompt) // 4
        
        def _req():
            with httpx.Client(timeout=120.0) as http:
                r = http.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"].strip()

        try:
            result = await asyncio.to_thread(_req)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            output_tokens = len(result) // 4
            
            # Phase 2: 追踪成本
            await self._track_vlm_cost(
                provider_id=prov.name,
                model_id=mdl.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                image_count=1,
                latency_ms=latency_ms,
                success=True
            )
            
            return result
        except Exception as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            
            # Phase 2: 追踪失败的成本
            await self._track_vlm_cost(
                provider_id=prov.name,
                model_id=mdl.model_id,
                input_tokens=input_tokens,
                output_tokens=0,
                image_count=1,
                latency_ms=latency_ms,
                success=False,
                error_message=str(e)
            )
            
            raise DomainInterpretationError(
                f"VLM call failed: {e}",
                domain_id=self.domain_id,
                stage="vlm_call",
                details={"provider": prov.name, "model": mdl.model_id, "error": str(e)}
            )

    async def _call_llm(
        self,
        prompt: str,
        context: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        skip_budget_check: bool = False
    ) -> str:
        """
        调用 LLM 进行文本生成
        
        Phase 2: 成本集成
        - 使用 Phase 1 Gateway
        - 调用前检查预算
        
        Args:
            prompt: 提示词
            context: 上下文（可选）
            provider: 指定 Provider（可选）
            model: 指定模型（可选）
            skip_budget_check: 是否跳过预算检查
            
        Returns:
            str: LLM 响应文本
        """
        from core.llm.gateway import LLMGateway

        # Phase 2: 预算检查
        if not skip_budget_check:
            content = prompt if not context else f"{prompt}\n\n{context}"
            estimated_input_tokens = len(content) // 4
            
            allowed, remaining = await self._check_budget_before_call(
                task_type="chat",
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=500
            )
            if not allowed:
                from core.llm.exceptions import BudgetExceededError
                raise BudgetExceededError(
                    f"Budget exceeded, remaining: ${remaining:.4f}",
                    scope="domain",
                    remaining=remaining
                )

        gateway = LLMGateway(
            provider=provider,
            model=model,
            enable_cost_tracking=True,
            routing_strategy="balanced" if not provider else "default"
        )

        try:
            return await gateway.chat(prompt, context)
        except Exception as e:
            raise DomainInterpretationError(
                f"LLM call failed: {e}",
                domain_id=self.domain_id,
                stage="llm_call",
                details={"provider": provider, "model": model, "error": str(e)}
            )

    async def _estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int = 500,
        image_count: int = 0,
        task_type: str = "chat"
    ) -> float:
        """
        预估调用成本
        
        Args:
            input_tokens: 输入 token 数
            output_tokens: 预估输出 token 数
            image_count: 图片数量
            task_type: 任务类型
            
        Returns:
            float: 预估成本（USD）
        """
        provider, model, cost = self.cost_estimator.get_cheapest_provider(
            task_type=task_type,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            require_domestic=True
        )
        
        if image_count > 0:
            # 添加图片成本
            cost += self.cost_estimator.estimate(
                provider, model, 0, 0, image_count
            )
        
        return cost

    async def _check_budget_before_call(
        self,
        task_type: str = "chat",
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500,
        image_count: int = 0
    ) -> tuple[bool, float]:
        """
        在调用前检查预算
        
        Phase 2: 成本集成
        - 预估调用成本
        - 检查是否超过预算
        
        Args:
            task_type: 任务类型 (chat, vision, embedding)
            estimated_input_tokens: 预估输入 token 数
            estimated_output_tokens: 预估输出 token 数
            image_count: 图片数量
            
        Returns:
            tuple[bool, float]: (是否允许调用, 剩余预算)
        """
        # 预估成本
        estimated_cost = await self._estimate_cost(
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens,
            image_count=image_count,
            task_type=task_type
        )
        
        # 检查预算
        allowed, remaining = await self.cost_tracker.check_budget()
        
        if not allowed:
            logger.warning(
                f"Budget check failed: estimated_cost=${estimated_cost:.4f}, "
                f"remaining=${remaining:.4f}"
            )
            return False, remaining
        
        # 检查预估成本是否超过剩余预算
        if estimated_cost > remaining:
            logger.warning(
                f"Estimated cost ${estimated_cost:.4f} exceeds remaining budget ${remaining:.4f}"
            )
            return False, remaining
        
        logger.debug(
            f"Budget check passed: estimated_cost=${estimated_cost:.4f}, "
            f"remaining=${remaining:.4f}"
        )
        return True, remaining

    async def _track_vlm_cost(
        self,
        provider_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        image_count: int,
        latency_ms: int,
        success: bool,
        error_message: str | None = None
    ) -> None:
        """
        追踪 VLM 调用成本
        
        Phase 2: 成本集成
        
        Args:
            provider_id: Provider 名称
            model_id: 模型 ID
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            image_count: 图片数量
            latency_ms: 延迟（毫秒）
            success: 是否成功
            error_message: 错误信息（可选）
        """
        from core.llm.cost_tracker import CostRecord
        
        cost_usd = self.cost_estimator.estimate(
            provider_id=provider_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count
        )
        
        record = CostRecord(
            provider_id=provider_id,
            model_id=model_id,
            task_type="vision",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message
        )
        
        await self.cost_tracker.track(record)
