from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .services import ModelGatewayService
from .supabase_service import SupabaseModelGatewayService
import os
from .schemas import (
    ModelCreate, ModelUpdate, ModelResponse, ModelWithMetrics, ModelListResponse,
    ModelTestRequest, ModelTestResponse, TaskBindingCreate, TaskBindingResponse,
    TaskBindingWithModel, DashboardStats, AuditLogListResponse,
    ModelFilterParams, PaginationParams, StackType, ModelCategory, ModelStatus, Environment
)
from .auth import get_current_user, authorize
 

router = APIRouter(prefix="/models", tags=["model-gateway"])


def svc(db: AsyncSession | None = None):
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        return SupabaseModelGatewayService()
    return ModelGatewayService(db)


@router.post("/", response_model=ModelResponse)
async def create_model(
    model_data: ModelCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new model configuration"""
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["providers:write"])
    service = svc(db)
    try:
        model = await service.create_model(
            model_data=model_data,
            user_id=current_user["id"],
            user_name=current_user["name"]
        )
        return model
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create model: {str(e)}")


@router.get("/", response_model=ModelListResponse)
async def list_models(
    stack: Optional[StackType] = Query(None, description="Filter by stack type"),
    category: Optional[ModelCategory] = Query(None, description="Filter by category"),
    environment: Optional[Environment] = Query(None, description="Filter by environment"),
    status: Optional[ModelStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search by name or endpoint"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List models with filtering and pagination"""
    service = svc(db)
    
    filters = ModelFilterParams(
        stack=stack,
        category=category,
        environment=environment,
        status=status,
        search=search
    )
    pagination = PaginationParams(page=page, page_size=page_size)
    
    try:
        return await service.list_models(filters, pagination)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/{model_id}", response_model=ModelWithMetrics)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get model by ID with latest metrics"""
    service = svc(db)
    
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


@router.put("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: UUID,
    model_data: ModelUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update model configuration"""
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["providers:write"])
    service = svc(db)
    model = await service.update_model(
        model_id=model_id,
        model_data=model_data,
        user_id=current_user["id"],
        user_name=current_user["name"]
    )
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return model


@router.delete("/{model_id}")
async def delete_model(
    model_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete model configuration"""
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["providers:write"])
    service = svc(db)
    success = await service.delete_model(
        model_id=model_id,
        user_id=current_user["id"],
        user_name=current_user["name"]
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {"message": "Model deleted successfully"}


@router.post("/{model_id}/test", response_model=ModelTestResponse)
async def test_model_connection(
    model_id: UUID,
    test_request: ModelTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Test model connection and performance"""
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["providers:write"])
    service = svc(db)
    try:
        return await service.test_model_connection(model_id, test_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model test failed: {str(e)}")


# Task Binding Routes
@router.post("/bindings", response_model=TaskBindingResponse)
async def create_task_binding(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create task to model binding"""
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["bindings:write"])
    service = svc(db)
    try:
        data = dict(payload or {})
        if "task_id" not in data and "task_type" in data:
            data = {
                "task_id": data.get("task_type", "chat"),
                "task_name": data.get("task_name", "default"),
                "model_id": data.get("primary_provider_id") or data.get("model_id"),
                "priority": data.get("priority", 1),
                "fallback_config": {},
                "environment": data.get("env") or data.get("environment", "dev"),
            }
        binding_data = TaskBindingCreate(**data)
        binding = await service.create_task_binding(
            binding_data=binding_data,
            user_id=current_user["id"],
            user_name=current_user["name"]
        )
        return binding
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create binding: {str(e)}")


@router.get("/bindings/{task_id}/{environment}", response_model=List[TaskBindingWithModel])
async def get_task_bindings(
    task_id: str,
    environment: Environment,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get task bindings for a specific task and environment"""
    service = svc(db)
    try:
        return await service.get_task_bindings(task_id, environment.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get bindings: {str(e)}")

# Credentials Routes
@router.get("/{provider_id}/credentials")
async def list_credentials(
    provider_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin", "read_only"], permissions=["credentials:read"])
    service = svc(db)
    try:
        return await service.list_credentials(str(provider_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list credentials: {str(e)}")


@router.post("/{provider_id}/credentials/{env}")
async def upsert_credentials(
    provider_id: UUID,
    env: Environment,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["credentials:write"])
    service = svc(db)
    try:
        return await service.upsert_credentials(str(provider_id), env.value, payload, current_user["id"], current_user["name"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upsert credentials: {str(e)}")


@router.delete("/{provider_id}/credentials/{env}")
async def delete_credentials(
    provider_id: UUID,
    env: Environment,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin"], permissions=["credentials:write"])
    service = svc(db)
    try:
        ok = await service.delete_credentials(str(provider_id), env.value, current_user["id"], current_user["name"])
        if not ok:
            raise HTTPException(status_code=404, detail="Credentials not found")
        return {"message": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete credentials: {str(e)}")


# Dashboard Routes
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics"""
    service = ModelGatewayService(db)
    
    try:
        return await service.get_dashboard_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


# Audit Log Routes
@router.get("/audit/logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get audit logs with filtering"""
    service = ModelGatewayService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    
    try:
        logs = await service.get_audit_logs(
            user_id=user_id,
            resource_type=resource_type,
            pagination=pagination
        )
        
        total = len(logs)
        return AuditLogListResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get audit logs: {str(e)}")


# Environment Versioning Routes
@router.get("/environments")
async def list_environments(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin", "read_only"])
    service = ModelGatewayService(db)
    envs = await service.list_environments()
    return envs


@router.get("/environments/{name}/versions")
async def list_env_versions(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin", "read_only"])
    service = ModelGatewayService(db)
    return await service.list_env_versions(name)


@router.post("/environments/{name}/versions")
async def create_env_version(
    name: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin"])
    service = ModelGatewayService(db)
    return await service.create_env_version(name, payload.get("config", {}), current_user["name"])


@router.post("/environments/{name}/versions/{version}/rollback")
async def rollback_env_version(
    name: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin"])
    service = ModelGatewayService(db)
    ok = await service.rollback_env_version(name, version, current_user["name"])
    if not ok:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"message": "rolled_back"}


@router.post("/environments/{name}/versions/{version}/apply")
async def apply_env_version(
    name: str,
    version: int,
    dry_run: bool = Query(True, description="Preview changes without applying"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    authorize(current_user, roles=["system_admin", "config_admin"])
    service = ModelGatewayService(db)
    try:
        return await service.apply_env_version(name, version, dry_run, current_user["name"])
    except ValueError:
        raise HTTPException(status_code=404, detail="Version not found")
