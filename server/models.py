import uuid
from sqlalchemy import Column, String, Integer, JSON, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func
from .database import Base

class Provider(Base):
    __tablename__ = "providers"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False) # llm, embedding, reranker, ocr
    base_url = Column(String(500))
    api_key = Column(String(500)) # Encrypted in production
    config_schema = Column(JSON, default={}) # JSON schema for model config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(PGUUID(as_uuid=True), nullable=False)
    model_id = Column(String(100), nullable=False) # Provider-specific model ID (e.g. gpt-4o)
    name = Column(String(100), nullable=False) # Display name
    type = Column(String(50), nullable=False) # embedding, chat, etc.
    parameters = Column(JSON, default={}) # Default params (temp, top_k)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
