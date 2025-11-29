from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str | None = Field(None, env="DATABASE_URL")
    milvus_uri: str | None = Field(None, env="MILVUS_URI")
    secret_key: str = Field("dev-secret", env="SECRET_KEY")

    gemini_api_key: str | None = Field(None, env="GEMINI_API_KEY")
    openai_api_key: str | None = Field(None, env="OPENAI_API_KEY")
    openrouter_api_key: str | None = Field(None, env="OPENROUTER_API_KEY")

    chat_temperature: float = Field(0.2, env="CHAT_TEMPERATURE")
    vector_weight: float = Field(0.6, env="VECTOR_WEIGHT")
    keyword_weight: float = Field(0.4, env="KEYWORD_WEIGHT")


settings = Settings()  # load from env

