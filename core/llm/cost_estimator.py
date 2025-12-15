"""
成本估算器 - 在调用前预估成本

Phase 1: 多云算力基础设施
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class CostEstimator:
    """成本估算器"""

    # 默认成本配置（每 1K tokens，USD）
    # 数据来源：各云厂商官方定价（2024-12）
    DEFAULT_COSTS: dict[str, dict[str, dict[str, float]]] = {
        "dashscope": {
            "qwen-max": {"input": 0.02, "output": 0.06},
            "qwen-max-latest": {"input": 0.02, "output": 0.06},
            "qwen-plus": {"input": 0.004, "output": 0.012},
            "qwen-plus-latest": {"input": 0.004, "output": 0.012},
            "qwen-turbo": {"input": 0.002, "output": 0.006},
            "qwen-turbo-latest": {"input": 0.002, "output": 0.006},
            "qwen-vl-max": {"input": 0.02, "output": 0.06},
            "qwen-vl-plus": {"input": 0.008, "output": 0.008},
            "text-embedding-v3": {"input": 0.0007, "output": 0.0},
        },
        "deepseek": {
            "deepseek-chat": {"input": 0.00014, "output": 0.00028},
            "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
            "deepseek-coder": {"input": 0.00014, "output": 0.00028},
        },
        "volcengine": {
            "doubao-pro-256k": {"input": 0.005, "output": 0.009},
            "doubao-pro-128k": {"input": 0.005, "output": 0.009},
            "doubao-pro-32k": {"input": 0.0008, "output": 0.002},
            "doubao-lite-128k": {"input": 0.0008, "output": 0.001},
            "doubao-lite-32k": {"input": 0.0003, "output": 0.0006},
        },
        "openai": {
            "gpt-4o": {"input": 0.0025, "output": 0.01},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
            "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
        },
        "azure": {
            "gpt-4o": {"input": 0.0025, "output": 0.01},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        },
        "anthropic": {
            "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
        },
        "gemini": {
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        },
    }

    # 图片处理成本（每张图片，USD）
    IMAGE_COSTS: dict[str, dict[str, float]] = {
        "dashscope": {
            "qwen-vl-max": 0.003,
            "qwen-vl-plus": 0.001,
        },
        "openai": {
            "gpt-4o": 0.00255,  # 低分辨率
            "gpt-4o-mini": 0.001275,
        },
    }

    def estimate(
        self,
        provider_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int = 0,
        image_count: int = 0
    ) -> float:
        """
        估算成本
        
        Args:
            provider_id: Provider 名称
            model_id: 模型 ID
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数（预估）
            image_count: 图片数量
            
        Returns:
            float: 预估成本（USD）
        """
        provider_id = provider_id.lower()
        model_id = model_id.lower()

        # 获取 token 成本
        provider_costs = self.DEFAULT_COSTS.get(provider_id, {})
        model_costs = provider_costs.get(model_id)
        
        if not model_costs:
            # 尝试模糊匹配
            for model_key in provider_costs:
                if model_key in model_id or model_id in model_key:
                    model_costs = provider_costs[model_key]
                    break
        
        if not model_costs:
            # 使用默认成本
            model_costs = {"input": 0.01, "output": 0.03}
            logger.debug(f"Using default costs for {provider_id}/{model_id}")

        input_cost = (input_tokens / 1000) * model_costs["input"]
        output_cost = (output_tokens / 1000) * model_costs["output"]

        # 图片成本
        image_cost = 0.0
        if image_count > 0:
            image_prices = self.IMAGE_COSTS.get(provider_id, {})
            image_price = image_prices.get(model_id, 0.002)  # 默认每张 $0.002
            image_cost = image_count * image_price

        return input_cost + output_cost + image_cost

    def get_cheapest_provider(
        self,
        task_type: str = "chat",
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500,
        require_domestic: bool = False
    ) -> tuple[str, str, float]:
        """
        获取最便宜的 Provider
        
        Args:
            task_type: 任务类型 (chat, embedding, vision)
            estimated_input_tokens: 预估输入 token 数
            estimated_output_tokens: 预估输出 token 数
            require_domestic: 是否要求国内 Provider
            
        Returns:
            tuple[str, str, float]: (provider_id, model_id, estimated_cost)
        """
        domestic_providers = {"dashscope", "deepseek", "volcengine"}
        
        min_cost = float("inf")
        best_provider = "dashscope"
        best_model = "qwen-turbo"

        for provider_id, models in self.DEFAULT_COSTS.items():
            # 过滤国内/国外
            if require_domestic and provider_id not in domestic_providers:
                continue

            for model_id, costs in models.items():
                # 过滤任务类型
                if task_type == "embedding" and "embedding" not in model_id:
                    continue
                if task_type == "vision" and "vl" not in model_id and "vision" not in model_id:
                    continue
                if task_type == "chat" and ("embedding" in model_id or "vl" in model_id):
                    continue

                cost = self.estimate(
                    provider_id, model_id,
                    estimated_input_tokens, estimated_output_tokens
                )
                if cost < min_cost:
                    min_cost = cost
                    best_provider = provider_id
                    best_model = model_id

        return best_provider, best_model, min_cost

    def get_providers_by_cost(
        self,
        task_type: str = "chat",
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500
    ) -> list[tuple[str, str, float]]:
        """
        按成本排序获取所有 Provider
        
        Returns:
            list[tuple[str, str, float]]: [(provider_id, model_id, cost), ...]
        """
        results = []

        for provider_id, models in self.DEFAULT_COSTS.items():
            for model_id, costs in models.items():
                # 过滤任务类型
                if task_type == "embedding" and "embedding" not in model_id:
                    continue
                if task_type == "vision" and "vl" not in model_id:
                    continue
                if task_type == "chat" and ("embedding" in model_id or "vl" in model_id):
                    continue

                cost = self.estimate(
                    provider_id, model_id,
                    estimated_input_tokens, estimated_output_tokens
                )
                results.append((provider_id, model_id, cost))

        return sorted(results, key=lambda x: x[2])


# 全局实例
_estimator: Optional[CostEstimator] = None


def get_cost_estimator() -> CostEstimator:
    """获取全局 CostEstimator 实例"""
    global _estimator
    if _estimator is None:
        _estimator = CostEstimator()
    return _estimator
