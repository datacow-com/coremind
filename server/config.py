from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str | None = None
    milvus_uri: str | None = None
    milvus_host: str | None = None
    milvus_port: int | None = None
    secret_key: str = "dev-secret"
    uploads_dir: str | None = None
    llm_provider: str | None = "gemini"
    vision_provider: str | None = "dashscope"
    web_search_provider: str | None = None  # tavily|serper|duckduckgo(default)
    web_search_timeout: float = 8.0
    # Usage & alerts
    max_tokens_per_day: int = 0
    max_calls_per_day: int = 0
    max_cost_per_day: float = 0.0
    alert_webhook_url: str | None = None
    cors_origins: list[str] = []
    stop_words_enabled: bool = False
    stop_words: list[str] = []
    term_weights: dict[str, float] = {}
    usage_dir: str | None = None
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60
    sse_heartbeat_interval: int = 0

    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    chat_temperature: float = 0.2
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    top_k_default: int = 5
    reranker_filter_threshold: float = 0.2
    grade_threshold: float = 0.35
    hallucination_threshold: float = 0.3
    rrf_k: int = 60
    web_search_enabled: bool = True
    use_base_retriever: bool = False

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

        if os.environ.get("UPLOADS_DIR"):
            return os.environ.get("UPLOADS_DIR")
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


settings = Settings()  # load from env
