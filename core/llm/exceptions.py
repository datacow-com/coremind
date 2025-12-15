"""
LLM Gateway 自定义异常

Phase 1: 多云算力基础设施
"""


class LLMGatewayError(Exception):
    """LLM Gateway 基础异常"""
    pass


class BudgetExceededError(LLMGatewayError):
    """预算超限异常"""
    
    def __init__(
        self,
        message: str,
        scope: str = "global",
        remaining: float = 0.0,
        daily_cost: float = 0.0,
        daily_limit: float = 0.0
    ):
        super().__init__(message)
        self.scope = scope
        self.remaining = remaining
        self.daily_cost = daily_cost
        self.daily_limit = daily_limit

    def __str__(self):
        return (
            f"{self.args[0]} "
            f"(scope={self.scope}, remaining=${self.remaining:.4f}, "
            f"daily_cost=${self.daily_cost:.4f}, limit=${self.daily_limit:.2f})"
        )


class ProviderUnavailableError(LLMGatewayError):
    """Provider 不可用异常"""
    
    def __init__(
        self,
        message: str,
        tried_providers: list[str] | None = None,
        last_error: str | None = None
    ):
        super().__init__(message)
        self.tried_providers = tried_providers or []
        self.last_error = last_error

    def __str__(self):
        providers_str = ", ".join(self.tried_providers) if self.tried_providers else "none"
        return f"{self.args[0]} (tried: {providers_str}, last_error: {self.last_error})"


class RateLimitError(LLMGatewayError):
    """速率限制异常"""
    
    def __init__(
        self,
        message: str,
        provider: str,
        retry_after: float | None = None
    ):
        super().__init__(message)
        self.provider = provider
        self.retry_after = retry_after


class ModelNotFoundError(LLMGatewayError):
    """模型未找到异常"""
    
    def __init__(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
