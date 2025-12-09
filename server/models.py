import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func

from .base import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(50), nullable=False)  # llm, embedding, reranker, ocr
    base_url = Column(String(500))
    api_key = Column(String(500))  # Encrypted in production
    config_schema = Column(JSON, default={})  # JSON schema for model config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(PGUUID(as_uuid=True), nullable=False)
    model_id = Column(String(100), nullable=False)  # Provider-specific model ID (e.g. gpt-4o)
    name = Column(String(100), nullable=False)  # Display name
    type = Column(String(50), nullable=False)  # embedding, chat, etc.
    parameters = Column(JSON, default={})  # Default params (temp, top_k)
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class StorageConfig(Base):
    __tablename__ = "storage_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    # Vector store
    vector_url = Column(String(500))
    vector_api_key = Column(String(500))
    vector_timeout = Column(Integer, default=10)
    vector_collection = Column(String(200))
    vector_dim = Column(Integer, default=1024)
    # Keyword store
    keyword_url = Column(String(500))
    keyword_user = Column(String(200))
    keyword_password = Column(String(200))
    keyword_timeout = Column(Integer, default=30)
    keyword_index = Column(String(200))
    # Blob store
    blob_type = Column(String(50), default="local")  # local/oss/minio
    blob_endpoint = Column(String(500))
    blob_access_key = Column(String(200))
    blob_secret_key = Column(String(200))
    blob_bucket = Column(String(200))
    blob_secure = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WebSearchConfig(Base):
    __tablename__ = "web_search_configs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False, unique=True)  # bocha/tavily/serper/duckduckgo
    base_url = Column(String(500))
    api_key = Column(String(500))
    timeout = Column(Integer, default=8)
    priority = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class KBConfig(Base):
    __tablename__ = "kb_configs"

    name = Column(String(200), primary_key=True)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class KBDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(String(200), primary_key=True)  # document id / filename key
    kb_name = Column(String(200), nullable=False)
    filename = Column(String(500), nullable=False)
    path = Column(String(1000), nullable=False)
    uploaded_at = Column(Integer, default=0)
    doc_metadata = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
