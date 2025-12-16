"""
Domains API - 领域管理 API

提供垂直领域管理和 KB 领域绑定接口：
- GET /api/domains - 列出所有领域
- GET /api/domains/{domain_id} - 获取领域详情
- GET /api/domains/{domain_id}/ontology - 获取领域本体
- POST /api/kb/{kb_name}/domain - 绑定领域到 KB
- GET /api/kb/{kb_name}/domain - 获取 KB 绑定的领域

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.domains.registry import get_domain_registry
from core.storage.kb_config import load_kb_config, save_kb_config


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════════════


class EntityDef(BaseModel):
    """Entity definition in ontology."""

    name: str
    description: str = ""
    attributes: list[str] = Field(default_factory=list)


class RelationDef(BaseModel):
    """Relation definition in ontology."""

    name: str
    source_type: str = Field(alias="from", default="")
    target_type: str = Field(alias="to", default="")
    description: str = ""

    class Config:
        populate_by_name = True


class OntologyResponse(BaseModel):
    """Ontology schema response."""

    domain_id: str
    version: str = "1.0"
    entities: list[EntityDef] = Field(default_factory=list)
    relations: list[RelationDef] = Field(default_factory=list)


class DomainInfo(BaseModel):
    """Domain information response."""

    id: str
    name: str
    description: str = ""
    icon: str = ""
    supported_formats: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)
    requires_gpu: bool = False
    recommended_vram_mb: int = 0
    has_ontology: bool = False


class DomainListResponse(BaseModel):
    """Response for listing all domains."""

    domains: list[DomainInfo]
    total: int


class DomainDetailResponse(BaseModel):
    """Response for domain detail."""

    domain: DomainInfo
    ontology: OntologyResponse | None = None


class DomainBindingRequest(BaseModel):
    """Request for binding domain to KB."""

    domain_id: str
    config: dict[str, Any] = Field(default_factory=dict)


class DomainBindingResponse(BaseModel):
    """Response for domain binding."""

    kb_name: str
    domain_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "bound"


class DomainBindingInfo(BaseModel):
    """Current domain binding info for a KB."""

    kb_name: str
    domain_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    is_bound: bool = False


class DependencyError(BaseModel):
    """Dependency error detail."""

    missing: list[str]
    message: str


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def _get_domain_info(domain_id: str) -> DomainInfo | None:
    """Get domain info from registry."""
    registry = get_domain_registry()
    
    if not registry.has_domain(domain_id):
        return None
    
    info = registry.get_domain_info(domain_id)
    if not info:
        return None
    
    # Get interpreter class for additional metadata
    interpreter_class = registry.get_interpreter_class(domain_id)
    
    # Build domain info
    return DomainInfo(
        id=domain_id,
        name=getattr(interpreter_class, "name", domain_id) if interpreter_class else domain_id,
        description=getattr(interpreter_class, "description", "") if interpreter_class else "",
        icon=getattr(interpreter_class, "icon", "📚") if interpreter_class else "📚",
        supported_formats=getattr(interpreter_class, "supported_formats", []) if interpreter_class else [],
        requires=getattr(interpreter_class, "requires", []) if interpreter_class else [],
        requires_gpu=info.get("requires_gpu", False),
        recommended_vram_mb=info.get("recommended_vram_mb", 0),
        has_ontology=info.get("has_ontology", False),
    )


def _get_ontology_response(domain_id: str) -> OntologyResponse | None:
    """Get ontology response from registry."""
    registry = get_domain_registry()
    ontology = registry.get_ontology(domain_id)
    
    if not ontology:
        return None
    
    # Convert entity types to EntityDef list
    entities: list[EntityDef] = []
    for name, entity_type in ontology.entity_types.items():
        entities.append(EntityDef(
            name=name,
            description=entity_type.description,
            attributes=list(entity_type.fields.keys()),
        ))
    
    # Convert relationships to RelationDef list
    relations: list[RelationDef] = []
    for rel in ontology.relationships:
        relations.append(RelationDef(
            name=rel.name,
            source_type=rel.source_type,
            target_type=rel.target_type,
            description=rel.description,
        ))
    
    return OntologyResponse(
        domain_id=ontology.domain_id,
        version=ontology.version,
        entities=entities,
        relations=relations,
    )


def _check_dependencies(domain_id: str, kb_config: dict[str, Any]) -> list[str]:
    """
    Check if KB meets domain dependencies.
    
    Returns list of missing dependencies.
    """
    registry = get_domain_registry()
    interpreter_class = registry.get_interpreter_class(domain_id)
    
    if not interpreter_class:
        return []
    
    requires = getattr(interpreter_class, "requires", [])
    if not requires:
        return []
    
    missing: list[str] = []
    capabilities = kb_config.get("capabilities", {})
    
    for req in requires:
        # Check if requirement is satisfied
        # Requirements can be capability IDs like "enhanced.ocr" or "pro.comic_recognition"
        parts = req.split(".")
        if len(parts) >= 2:
            category = parts[0]
            cap_key = ".".join(parts[1:])
            cat_caps = capabilities.get(category, {})
            cap_config = cat_caps.get(cap_key, {})
            
            # Check if capability is enabled
            if isinstance(cap_config, bool):
                if not cap_config:
                    missing.append(req)
            elif isinstance(cap_config, dict):
                if not cap_config.get("enabled", False):
                    missing.append(req)
            else:
                missing.append(req)
        else:
            # Simple capability check
            found = False
            for cat_caps in capabilities.values():
                if isinstance(cat_caps, dict):
                    cap_config = cat_caps.get(req, {})
                    if isinstance(cap_config, bool) and cap_config:
                        found = True
                        break
                    elif isinstance(cap_config, dict) and cap_config.get("enabled", False):
                        found = True
                        break
            if not found:
                missing.append(req)
    
    return missing


# ═══════════════════════════════════════════════════════════════════════════════
# Router and Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

router = APIRouter(tags=["domains"])


@router.get("/domains", response_model=DomainListResponse)
async def list_domains() -> DomainListResponse:
    """
    列出所有已注册的领域
    
    Requirements: 3.1
    """
    registry = get_domain_registry()
    domain_ids = registry.list_domains()
    
    domains: list[DomainInfo] = []
    for domain_id in domain_ids:
        info = _get_domain_info(domain_id)
        if info:
            domains.append(info)
    
    return DomainListResponse(
        domains=domains,
        total=len(domains),
    )


@router.get("/domains/{domain_id}", response_model=DomainDetailResponse)
async def get_domain(domain_id: str) -> DomainDetailResponse:
    """
    获取领域详情
    
    Requirements: 3.1
    """
    info = _get_domain_info(domain_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain_id}")
    
    ontology = _get_ontology_response(domain_id)
    
    return DomainDetailResponse(
        domain=info,
        ontology=ontology,
    )


@router.get("/domains/{domain_id}/ontology", response_model=OntologyResponse)
async def get_domain_ontology(domain_id: str) -> OntologyResponse:
    """
    获取领域本体定义
    
    Requirements: 3.2
    """
    registry = get_domain_registry()
    
    if not registry.has_domain(domain_id):
        raise HTTPException(status_code=404, detail=f"Domain not found: {domain_id}")
    
    ontology = _get_ontology_response(domain_id)
    if not ontology:
        raise HTTPException(status_code=404, detail=f"Ontology not found for domain: {domain_id}")
    
    return ontology


@router.post("/kb/{kb_name}/domain", response_model=DomainBindingResponse)
async def bind_domain_to_kb(kb_name: str, request: DomainBindingRequest) -> DomainBindingResponse:
    """
    绑定领域到 KB
    
    Requirements: 3.3, 3.5
    """
    registry = get_domain_registry()
    
    # Check if domain exists
    if not registry.has_domain(request.domain_id):
        raise HTTPException(status_code=404, detail=f"Domain not found: {request.domain_id}")
    
    # Load KB config
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e
    
    # Check dependencies (Requirements 3.5)
    missing_deps = _check_dependencies(request.domain_id, kb_config)
    if missing_deps:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "DEPENDENCY_NOT_MET",
                "message": f"Missing dependencies for domain {request.domain_id}",
                "missing": missing_deps,
            },
        )
    
    # Update KB config with domain binding
    kb_config["domain"] = {
        "domain_id": request.domain_id,
        "config": request.config,
    }
    
    # Save KB config
    try:
        save_kb_config(kb_name, kb_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save KB config: {e}") from e
    
    return DomainBindingResponse(
        kb_name=kb_name,
        domain_id=request.domain_id,
        config=request.config,
        status="bound",
    )


@router.get("/kb/{kb_name}/domain", response_model=DomainBindingInfo)
async def get_kb_domain(kb_name: str) -> DomainBindingInfo:
    """
    获取 KB 绑定的领域
    
    Requirements: 3.4
    """
    # Load KB config
    try:
        kb_config = load_kb_config(kb_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"KB not found: {kb_name}") from e
    
    # Get domain binding
    domain_binding = kb_config.get("domain", {})
    
    if not domain_binding or not domain_binding.get("domain_id"):
        return DomainBindingInfo(
            kb_name=kb_name,
            domain_id=None,
            config={},
            is_bound=False,
        )
    
    return DomainBindingInfo(
        kb_name=kb_name,
        domain_id=domain_binding.get("domain_id"),
        config=domain_binding.get("config", {}),
        is_bound=True,
    )
