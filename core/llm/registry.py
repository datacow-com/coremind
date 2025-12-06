from core.llm.gateway import LLMGateway


def get_llm_gateway(provider: str | None = None, model: str | None = None) -> LLMGateway:
    """
    Thin registry wrapper for LLMGateway to allow per-request override without duplicating logic.
    """
    return LLMGateway(provider=provider, model=model)
