from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str | None = None
    milvus_uri: str | None = None
    milvus_host: str | None = None
    milvus_port: int | None = None
    secret_key: str = "dev-secret"
    uploads_dir: str | None = None
    llm_provider: str | None = "dashscope"
    vision_provider: str | None = "dashscope"
    web_search_provider: str | None = None  # tavily|serper|duckduckgo(default)
    web_search_timeout: float = 8.0
    # Usage & alerts
    max_tokens_per_day: int = 0
    max_calls_per_day: int = 0
    max_cost_per_day: float = 0.0
    alert_webhook_url: str | None = None
    cors_origins: list[str] = []
    redis_url: str | None = None
    stop_words_enabled: bool = False
    stop_words: list[str] = []
    term_weights: dict[str, float] = {}
    usage_dir: str | None = None
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60
    sse_heartbeat_interval: int = 0
    upload_max_bytes: int = 20 * 1024 * 1024
    upload_allowed_mime_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/markdown",
        "text/plain",
        "image/png",
        "image/jpeg",
    ]

    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    chat_temperature: float = 0.2
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    top_k_default: int = 5
    candidate_k: int = 50
    reranker_filter_threshold: float = 0.2
    rerank_base_weight: float = 0.7
    rerank_model_weight: float = 0.3
    # Telemetry
    otel_trace_sample_ratio: float = 1.0
    trace_sensitive_keys: list[str] = []
    # Retrieval/Rerank defaults (can be overridden by KB or metadata)
    rrf_k: int = 60
    # Required in prod
    metrics_token: str | None = None
    metrics_allow_ips: list[str] = []
    force_vector_backend: str | None = None  # optional override to disable auto detection
    # Additional validation limits
    image_max_pixels: int = 50_000_000  # max area for images
    markdown_max_bytes: int = 2 * 1024 * 1024  # 2MB for markdown/text uploads
    markdown_max_lines: int = 5000
    grade_threshold: float = 0.35
    hallucination_threshold: float = 0.3
    rrf_k: int = 60
    web_search_enabled: bool = True
    use_base_retriever: bool = False
    # Parser & vision toggles
    semantic_chunking: bool = False
    parser_denoise: bool = False
    yolo_enabled: bool = False
    yolo_model: str | None = None
    layoutlm_enabled: bool = False
    layoutlm_model: str | None = None
    layoutlm_class_model: str | None = None
    # Embedding provider
    embedding_model: str | None = "BAAI/bge-m3"
    domestic_only: bool = True
    vector_backend: str | None = None
    keyword_backend: str | None = None
    # Elasticsearch
    elasticsearch_url: str | None = None
    elasticsearch_index: str | None = None
    # Qdrant
    qdrant_url: str | None = None
    qdrant_host: str | None = None
    qdrant_port: int | None = None
    qdrant_collection: str | None = None
    # LLM retry settings
    llm_retry_attempts: int = 2
    llm_retry_backoff_ms: int = 500
    # Upload safety
    # （保留上方字段，以下去重）
    # Rate limit backend
    # SSE / streaming guards
    # Circuit breaker for external calls

    @property
    def milvus_uri_resolved(self) -> str | None:
        if self.milvus_uri:
            return self.milvus_uri
        if self.milvus_host and self.milvus_port:
            return f"http://{self.milvus_host}:{self.milvus_port}"
        return None

    @property
    def uploads_dir_resolved(self) -> str:
        import os

        v = os.environ.get("UPLOADS_DIR")
        if v:
            return v
        if self.uploads_dir:
            return self.uploads_dir
        import os as _os

        return _os.path.join(_os.getcwd(), "data", "uploads")

    @property
    def usage_dir_resolved(self) -> str:
        import os

        if self.usage_dir:
            return self.usage_dir
        base = os.path.join(os.getcwd(), "data", "usage")
        return base

    @property
    def cors_origins_resolved(self) -> list[str]:
        # In prod，必须显式配置；在 dev 回退本地前端
        if self.cors_origins:
            return self.cors_origins
        env = (self.app_env or os.environ.get("APP_ENV", "dev")).lower()
        if env == "prod":
            return []
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def rate_limit_enabled_resolved(self) -> bool:
        # prod 默认开启；dev 遵循配置
        env = (self.app_env or os.environ.get("APP_ENV", "dev")).lower()
        if env == "prod":
            return True
        return bool(self.rate_limit_enabled)


settings = Settings()  # load from env
