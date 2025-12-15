"""
Vertical Domain Interpretation Framework

Phase 2: 垂直领域增强
提供统一的领域解读基座，支持命理分析、漫画解读等垂直场景的专业化处理。
"""

from core.domains.registry import DomainRegistry, get_domain_registry
from core.domains.base_interpreter import BaseDomainInterpreter, InterpretationResult
from core.domains.ontology_schema import OntologySchema, EntityType, Relationship, FieldSpec
from core.domains.narrative_engine import NarrativeEngine
from core.domains.exceptions import (
    DomainError,
    DomainInterpretationError,
    OntologyValidationError,
    DomainNotFoundError,
)

__all__ = [
    # Registry
    "DomainRegistry",
    "get_domain_registry",
    # Interpreter
    "BaseDomainInterpreter",
    "InterpretationResult",
    # Ontology
    "OntologySchema",
    "EntityType",
    "Relationship",
    "FieldSpec",
    # Narrative
    "NarrativeEngine",
    # Exceptions
    "DomainError",
    "DomainInterpretationError",
    "OntologyValidationError",
    "DomainNotFoundError",
]
