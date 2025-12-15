"""
Domain Framework Exceptions

Phase 2: 垂直领域增强
"""


class DomainError(Exception):
    """领域框架基础异常"""
    pass


class DomainInterpretationError(DomainError):
    """领域解读错误"""

    def __init__(
        self,
        message: str,
        domain_id: str,
        stage: str,
        details: dict | None = None
    ):
        super().__init__(message)
        self.domain_id = domain_id
        self.stage = stage
        self.details = details or {}

    def __str__(self) -> str:
        return (
            f"{self.args[0]} "
            f"(domain={self.domain_id}, stage={self.stage}, details={self.details})"
        )


class OntologyValidationError(DomainError):
    """本体验证错误"""

    def __init__(self, message: str, violations: list[str]):
        super().__init__(message)
        self.violations = violations

    def __str__(self) -> str:
        violations_str = "; ".join(self.violations[:5])
        if len(self.violations) > 5:
            violations_str += f"... and {len(self.violations) - 5} more"
        return f"{self.args[0]} (violations: {violations_str})"


class DomainNotFoundError(DomainError):
    """领域未找到错误"""

    def __init__(self, domain_id: str):
        super().__init__(f"Domain not found: {domain_id}")
        self.domain_id = domain_id
