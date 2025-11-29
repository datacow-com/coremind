from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://user:password@localhost:5432/omnirag"
    
    # Milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_collection_name: str = "omnirag_chunks"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # LLM APIs
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Vector model
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Processing
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Security
    secret_key: str = "your-secret-key-here"
    access_token_expire_minutes: int = 30
    
    # Web search
    tavily_api_key: Optional[str] = None
    serper_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()