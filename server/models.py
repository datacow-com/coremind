import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Model(Base):
    __tablename__ = "models"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    stack = Column(String(20), nullable=False)  # cn, overseas
    category = Column(String(50), nullable=False)  # llm, embedding, reranker
    endpoint = Column(String(500), nullable=False)
    auth_config = Column(JSON, nullable=False, default={})
    parameters = Column(JSON, nullable=False, default={})
    priority = Column(Integer, default=1)
    status = Column(String(20), default="active")  # active, inactive, testing
    environment = Column(String(20), default="dev")  # dev, test, prod
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_models_stack", "stack"),
        Index("idx_models_category", "category"),
        Index("idx_models_status", "status"),
        Index("idx_models_environment", "environment"),
    )


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(PGUUID(as_uuid=True), nullable=False)
    ttft = Column(Float, nullable=False, default=0)  # Time to first token
    throughput = Column(Float, nullable=False, default=0)  # tokens per second
    error_rate = Column(Float, nullable=False, default=0)
    quality_score = Column(Float, nullable=False, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_model_metrics_model_id", "model_id"),
        Index("idx_model_metrics_recorded_at", "recorded_at"),
    )


class TaskBinding(Base):
    __tablename__ = "task_bindings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), nullable=False)
    task_name = Column(String(200), nullable=False)
    model_id = Column(PGUUID(as_uuid=True), nullable=False)
    priority = Column(Integer, nullable=False, default=1)
    fallback_config = Column(JSON, default={})
    environment = Column(String(20), default="dev")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_task_bindings_task_id", "task_id"),
        Index("idx_task_bindings_model_id", "model_id"),
        Index("idx_task_bindings_environment", "environment"),
    )


class ModelCredential(Base):
    __tablename__ = "model_credentials"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(PGUUID(as_uuid=True), nullable=False)
    env = Column(String(20), nullable=False)  # dev, test, prod
    auth_type = Column(String(20), default="api_key")
    key_name = Column(String(200))
    key_last4 = Column(String(10))
    secret_ciphertext = Column(String(4096))
    rate_limit_rps = Column(Integer)
    quota_limit = Column(Integer)
    quota_window = Column(String(50))
    billing_info = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_model_credentials_provider_env", "provider_id", "env", unique=True),
    )


class Environment(Base):
    __tablename__ = "environments"

    name = Column(String(50), primary_key=True)
    description = Column(Text)
    is_production = Column(Boolean, default=False)
    config_schema = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EnvironmentVersion(Base):
    __tablename__ = "environment_versions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    version = Column(Integer, nullable=False)
    config = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(100))

    __table_args__ = (
        Index("idx_env_versions_name_version", "name", "version", unique=True),
        Index("idx_env_versions_name", "name"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    user_name = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100))
    changes = Column(JSON, default={})
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_created_at", "created_at"),
    )
