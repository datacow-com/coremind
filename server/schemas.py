from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StackType(str, Enum):
    CN = "cn"
    OVERSEAS = "overseas"


class ModelCategory(str, Enum):
    LLM = "llm"
    EMBEDDING = "embedding"
    RERANKER = "reranker"


class ModelStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"


class Environment(str, Enum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class AuthConfig(BaseModel):
    type: str = Field(..., description="Authentication type: api_key, oauth, basic")
    api_key: str | None = Field(None, description="API key for authentication")
    username: str | None = Field(None, description="Username for basic auth")
    password: str | None = Field(None, description="Password for basic auth")
    client_id: str | None = Field(None, description="Client ID for OAuth")
    client_secret: str | None = Field(None, description="Client secret for OAuth")


class ModelParameters(BaseModel):
    max_tokens: int | None = Field(None, description="Maximum tokens")
    temperature: float | None = Field(None, ge=0.0, le=2.0, description="Temperature")
    top_p: float | None = Field(None, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(None, ge=-2.0, le=2.0)
    stop_sequences: list[str] | None = Field(None, description="Stop sequences")


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Model name")
    stack: StackType = Field(..., description="Model stack: cn or overseas")
    category: ModelCategory = Field(..., description="Model category")
    endpoint: str = Field(..., min_length=1, max_length=500, description="API endpoint")
    auth_config: AuthConfig = Field(
        default_factory=lambda: AuthConfig(type="none"), description="Authentication configuration"
    )
    parameters: ModelParameters = Field(
        default_factory=lambda: ModelParameters(), description="Model parameters"
    )
    priority: int = Field(1, ge=1, le=100, description="Priority level")
    status: ModelStatus = Field(ModelStatus.ACTIVE, description="Model status")
    environment: Environment = Field(Environment.DEV, description="Environment")


class ModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    stack: StackType | None = None
    category: ModelCategory | None = None
    endpoint: str | None = Field(None, min_length=1, max_length=500)
    auth_config: AuthConfig | None = None
    parameters: ModelParameters | None = None
    priority: int | None = Field(None, ge=1, le=100)
    status: ModelStatus | None = None
    environment: Environment | None = None


class ModelResponse(BaseModel):
    id: UUID
    name: str
    stack: StackType
    category: ModelCategory
    endpoint: str
    auth_config: AuthConfig
    parameters: ModelParameters
    priority: int
    status: ModelStatus
    environment: Environment
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ModelMetrics(BaseModel):
    ttft: float = Field(..., description="Time to first token (seconds)")
    throughput: float = Field(..., description="Tokens per second")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Quality score")

    model_config = ConfigDict(from_attributes=True)


class ModelWithMetrics(ModelResponse):
    metrics: ModelMetrics | None = None


class ModelTestRequest(BaseModel):
    prompt: str = Field("hello", min_length=1, description="Test prompt")
    max_tokens: int | None = Field(100, ge=1, le=4096)


class ModelTestResponse(BaseModel):
    status: str = Field(..., description="Test status: success, failed, timeout")
    latency: float = Field(..., description="Total latency in milliseconds")
    ttft: float | None = Field(None, description="Time to first token in seconds")
    error: str | None = Field(None, description="Error message if failed")


class TaskBindingCreate(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=100, description="Task ID")
    task_name: str = Field(..., min_length=1, max_length=200, description="Task name")
    model_id: UUID = Field(..., description="Model ID")
    priority: int = Field(1, ge=1, le=100, description="Binding priority")
    fallback_config: dict[str, Any] | None = Field(
        default_factory=dict, description="Fallback configuration"
    )
    environment: Environment = Field(Environment.DEV, description="Environment")
    model_config = ConfigDict(protected_namespaces=())


class TaskBindingResponse(BaseModel):
    id: UUID
    task_id: str
    task_name: str
    model_id: UUID
    priority: int
    fallback_config: dict[str, Any]
    environment: Environment
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class TaskBindingWithModel(TaskBindingResponse):
    model: ModelResponse
    model_config = ConfigDict(protected_namespaces=())


class EnvironmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Environment name")
    description: str | None = Field(None, max_length=500, description="Environment description")
    is_production: bool = Field(False, description="Is production environment")
    config_schema: dict[str, Any] | None = Field(
        default_factory=dict, description="Configuration schema"
    )


class EnvironmentResponse(BaseModel):
    name: str
    description: str | None
    is_production: bool
    config_schema: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str
    action: str
    resource_type: str
    resource_id: str | None
    changes: dict[str, Any]
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Page size")


class ModelListResponse(BaseModel):
    models: list[ModelWithMetrics]
    total: int
    page: int
    page_size: int


class TaskBindingListResponse(BaseModel):
    bindings: list[TaskBindingWithModel]
    total: int
    page: int
    page_size: int


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class ModelFilterParams(BaseModel):
    stack: StackType | None = None
    category: ModelCategory | None = None
    environment: Environment | None = None
    status: ModelStatus | None = None
    search: str | None = Field(None, description="Search by name or endpoint")


class DashboardStats(BaseModel):
    total_models: int
    active_models: int
    cn_models: int
    overseas_models: int
    avg_ttft: float
    avg_throughput: float
    avg_error_rate: float


# Existing RAG schemas
class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    estimated_time: int


class Source(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_name: str
    page_number: int


class ChatRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    top_k: int | None = 5
    candidate_k: int | None = None
    document_ids: list[str] | None = None
    vector_weight: float | None = None
    keyword_weight: float | None = None
    web_search_enabled: bool | None = None
    reranker_threshold: float | None = None
    lang_hint: str | None = None
    kb_name: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    conversation_id: str
    message_id: str
