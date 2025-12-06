from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from server.database import get_db
from server.models import Provider, ModelConfig

router = APIRouter()

# --- Pydantic Schemas ---

class ProviderCreate(BaseModel):
    name: str
    category: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    config_schema: Optional[dict] = {}

class ProviderRead(ProviderCreate):
    id: str
    is_active: bool

class ModelConfigCreate(BaseModel):
    provider_id: str
    model_id: str
    name: str
    type: str
    parameters: Optional[dict] = {}
    is_default: bool = False

class ModelConfigRead(ModelConfigCreate):
    id: str
    is_active: bool

# --- Provider Endpoints ---

@router.get("/providers", response_model=List[ProviderRead])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider))
    return result.scalars().all()

@router.post("/providers", response_model=ProviderRead)
async def create_provider(provider: ProviderCreate, db: AsyncSession = Depends(get_db)):
    db_provider = Provider(**provider.dict())
    db.add(db_provider)
    await db.commit()
    await db.refresh(db_provider)
    return db_provider

@router.patch("/providers/{provider_id}")
async def update_provider(provider_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    for key, value in payload.items():
        setattr(provider, key, value)
    
    await db.commit()
    await db.refresh(provider)
    return provider

# --- Model Config Endpoints ---

@router.get("/models", response_model=List[ModelConfigRead])
async def list_models(type: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    query = select(ModelConfig).where(ModelConfig.is_active == True)
    if type:
        query = query.where(ModelConfig.type == type)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/models", response_model=ModelConfigRead)
async def create_model(model: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    db_model = ModelConfig(**model.dict())
    db.add(db_model)
    await db.commit()
    await db.refresh(db_model)
    return db_model

@router.delete("/models/{model_id}")
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()
    if model:
        await db.delete(model)
        await db.commit()
    return {"status": "ok"}

