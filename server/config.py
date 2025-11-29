from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str | None = None
    milvus_uri: str | None = None
    milvus_host: str | None = None
    milvus_port: int | None = None
    secret_key: str = "dev-secret"

    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    chat_temperature: float = 0.2
    vector_weight: float = 0.6
    keyword_weight: float = 0.4

    @property
    def milvus_uri_resolved(self) -> str | None:
        if self.milvus_uri:
            return self.milvus_uri
        if self.milvus_host and self.milvus_port:
            return f"http://{self.milvus_host}:{self.milvus_port}"
        return None


settings = Settings()  # load from env
