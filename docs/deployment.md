# OmniRAG Deployment Guide

## Environment Variables

OmniRAG relies on environment variables for configuration. Below is a comprehensive list of supported variables.

### General
- `APP_ENV`: Application environment mode (e.g., `prod`, `dev`, `test`). Defaults to `dev`.
- `SECRET_KEY`: **Required**. A secure random string (min 16 chars) for JWT encryption and session security.

### Database
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:pass@host:5432/dbname`).

### Storage & Indexing

#### Blob Storage
- `BLOB_STORE_TYPE`: Storage backend type. Options: `local` (default), `minio`, `oss`.
- `UPLOADS_DIR`: Path for local file storage (default: `./data/uploads`).

**MinIO / S3 Compatible:**
- `MINIO_ENDPOINT`: MinIO server endpoint (e.g., `localhost:9000`).
- `MINIO_ROOT_USER`: Access Key.
- `MINIO_ROOT_PASSWORD`: Secret Key.
- `MINIO_BUCKET`: Bucket name (default: `omnirag`).
- `MINIO_SECURE`: Set to `true` for HTTPS (default: `false`).

**Aliyun OSS:**
- `OSS_ACCESS_KEY_ID`: Access Key ID.
- `OSS_ACCESS_KEY_SECRET`: Access Key Secret.
- `OSS_ENDPOINT`: OSS Endpoint (e.g., `oss-cn-hangzhou.aliyuncs.com`).
- `OSS_BUCKET`: Bucket name.

#### Vector Store
- `VECTOR_BACKEND`: Vector database backend. Options: `qdrant` (default), `milvus`, `auto`.
- `QDRANT_URL`: Qdrant server URL (default: `http://localhost:6333`).
- `QDRANT_API_KEY`: (Optional) API Key for Qdrant Cloud or secure instance.
- `QDRANT_COLLECTION`: Default collection name prefix.

**Milvus (Legacy/Alternative):**
- `MILVUS_HOST`: Milvus host (default: `localhost`).
- `MILVUS_PORT`: Milvus port (default: `19530`).

#### Keyword Store
- `KEYWORD_BACKEND`: Keyword search backend. Options: `elasticsearch` (default), `local` (BM25 in-memory), `disabled`.
- `ELASTICSEARCH_URL`: Elasticsearch URL (default: `http://localhost:9200`).
- `ELASTICSEARCH_USER`: (Optional) Username.
- `ELASTICSEARCH_PASSWORD`: (Optional) Password.
- `ELASTICSEARCH_INDEX`: Default index name prefix.

#### Caching & Queue
- `REDIS_URL`: Redis connection string (e.g., `redis://localhost:6379/0`). Required for task queues and caching.

### Models & Providers

#### LLM Provider
- `LLM_PROVIDER`: Primary LLM provider. Options: `dashscope`, `openai`, `gemini`, `anthropic`.

**DashScope (Aliyun Qwen):**
- `DASHSCOPE_API_KEY`: API Key.
- `DASHSCOPE_CHAT_MODEL`: Model name (default: `qwen-plus`).
- `DASHSCOPE_COMPAT_URL`: OpenAI-compatible endpoint URL.

**OpenAI:**
- `OPENAI_API_KEY`: API Key.
- `OPENAI_CHAT_MODEL`: Model name (default: `gpt-4o-mini`).

#### Embedding & Rerank
- `EMBEDDING_MODEL`: Model ID for embedding (default: `BAAI/bge-m3`).
- `RERANKER_PROVIDER`: Reranker provider. Options: `cross_encoder` (local), `cohere`.
- `RERANKER_MODEL`: Model ID for local reranker (default: `BAAI/bge-reranker-v2-m3`).

#### Web Search
- `WEB_SEARCH_PROVIDER`: Search provider. Options: `duckduckgo` (default), `serper`, `tavily`.
- `SERPER_API_KEY`: API Key for Serper (if used).

### Observability
- `ENABLE_OTEL`: Enable OpenTelemetry tracing (default: `false`).
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP collector endpoint (default: `http://localhost:4317`).
- `OTEL_SERVICE_NAME`: Service name for traces (default: `omnirag-core`).

## Docker Deployment

1.  **Prepare Environment**:
    Copy the variable list above into a `.env` file in the project root and fill in your secrets.

2.  **Start Services**:
    ```bash
    docker-compose up -d
    ```
    This will start Postgres, Qdrant, Elasticsearch, Redis, MinIO, Backend, Frontend, and Nginx.

3.  **Verify**:
    - Frontend: http://localhost:3500
    - Backend API: http://localhost:3500/api/health
    - MinIO Console: http://localhost:3511

