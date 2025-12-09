# OmniRAG Project Rules

## Project Context
OmniRAG is a high-performance RAG (Retrieval-Augmented Generation) system built with **FastAPI** (Server) and **LangGraph** (Core Logic).

## Architectural Guidelines

### 1. Module Boundaries
-   **Core (`core/`)**: Contains all business logic, algorithms, and pipelines. Must be framework-agnostic where possible.
-   **Server (`server/`)**: Contains FastAPI routes, database models, and API schemas. **Server depends on Core. Core NEVER depends on Server.**
-   **Storage (`core/storage/`)**: Use the `index_router.py` facade. Do not import `QdrantClient` or `Elasticsearch` directly in business logic nodes.

### 2. Dependency Management
-   **No Circular Imports**:
    -   Be extremely cautious with `server/database.py` and `server/models.py`.
    -   **Rule**: define `Base` in a separate `server/base.py` or generic module if shared.
    -   **Rule**: Do not import `server.models` inside `server.database` at the top level.
-   **No "God Objects"**: Avoid massive state objects. Use `TypedDict` (like `RAGState`, `IngestState`) for passing data between LangGraph nodes.

### 3. Database & Models (SQLAlchemy)
-   **Reserved Keywords**: DO NOT name columns `metadata`. Use `doc_metadata` or similar. (`metadata` is reserved by SQLAlchemy Declarative API).
-   **Async First**: Use `asyncio` and `AsyncSession` for all DB interactions.

## Coding Standards

### Python
-   **Type Hinting**: All function signatures must have type hints. Use `typing.Optional`, `typing.List`, `typing.Dict`.
-   **Pydantic**: Use Pydantic models for API request/response bodies and configuration.
-   **Error Handling**:
    -   Use `try/except` blocks in Ingestion nodes to prevent single-file failures from crashing a batch.
    -   Log errors with `logging.exception` including `request_id`.

### LangGraph / Logic
-   **State Immutability**: Treat state dicts as immutable where possible; return *updates* rather than mutating in place if unclear.
-   **Retrieval Fragmentation**:
    -   **V4 Graph** (`core/retrieval/graph.py`) is the target architecture.
    -   **Legacy** (`core/nodes/retrieve.py`) is deprecated. Prefer implementing new logic in V4.

## Development Workflow
-   **Startup**: `bash scripts/dev.sh`
-   **Testing**: `pytest` for unit tests.
-   **Linting**: `ruff check .`
-   **Formatting**: `ruff format .`

## Anti-Patterns to Avoid
1.  **Dict Soup**: Passing raw dictionaries without `TypedDict` definitions.
2.  **Hardcoded Paths**: Use `settings.uploads_dir_resolved` instead of hardcoded strings.
3.  **Strict Coupling**: Importing concrete vector store clients (e.g. `qdrant_client`) directly into `core/nodes`. Always use `core/storage` abstraction.
