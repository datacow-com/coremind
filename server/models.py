import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, Numeric, String, Text, UniqueConstraint
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

    # Phase 1 扩展字段
    priority = Column(Integer, default=10)  # 路由优先级，数字越小优先级越高
    endpoints = Column(JSON, default={})  # {"chat": "...", "embedding": "...", "vision": "..."}
    rate_limits = Column(JSON, default={})  # {"rpm": 1000, "tpm": 1000000}
    is_healthy = Column(Boolean, default=True)
    last_health_check = Column(DateTime(timezone=True))
    circuit_breaker_failures = Column(Integer, default=0)
    circuit_breaker_open_until = Column(DateTime(timezone=True))


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


# ============================================================================
# Phase 1: 多云算力基础设施模型
# ============================================================================


class ComputeCostRecord(Base):
    """API 调用成本记录"""
    __tablename__ = "compute_cost_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(100), nullable=False)
    channel_id = Column(String(100))
    user_id = Column(String(100))
    provider_id = Column(String(100), nullable=False)
    model_id = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)  # chat, embedding, vision
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    image_count = Column(Integer, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False)
    latency_ms = Column(Integer)
    cached = Column(Boolean, default=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BudgetConfig(Base):
    """预算配置"""
    __tablename__ = "budget_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(50), nullable=False)  # global, channel, user
    scope_id = Column(String(100))  # channel_id 或 user_id，global 时为 NULL
    daily_limit = Column(Numeric(10, 2))
    monthly_limit = Column(Numeric(10, 2))
    alert_threshold = Column(Numeric(3, 2), default=0.80)  # 80% 时告警
    hard_stop_threshold = Column(Numeric(3, 2), default=0.95)  # 95% 时停止
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('scope', 'scope_id', name='uq_budget_scope'),
    )


class DomainConfig(Base):
    """领域配置（Phase 2+ 预留）"""
    __tablename__ = "domain_configs"

    id = Column(String(100), primary_key=True)  # metaphysics_chinese, comic_four_panel
    name = Column(String(200), nullable=False)
    name_en = Column(String(200))
    ontology = Column(JSON, nullable=False)  # 领域本体定义
    visual_schema = Column(JSON)  # 视觉模式定义
    narrative_schema = Column(JSON)  # 叙事模式定义
    interpretation_rules = Column(JSON)  # 解读规则
    gpu_requirements = Column(JSON)  # {"min_vram_gb": 8, "recommended_vram_gb": 24}
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
