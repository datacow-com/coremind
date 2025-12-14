from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import TypedDict

# --- Pydantic Models for API / Strategy Config ---


class ChunkingStrategy(BaseModel):
    """
    分块策略配置
    
    P0 Fix: 添加字段验证确保 chunk_size > 0, chunk_overlap >= 0
    P1 Fix: 添加 model_validator 确保 chunk_overlap < chunk_size
    """
    mode: Literal["fixed", "semantic", "layout_aware", "table_first"] = "fixed"
    chunk_size: int = Field(default=512, gt=0, description="Chunk size must be positive")
    chunk_overlap: int = Field(default=50, ge=0, description="Chunk overlap must be non-negative")
    preserve_tables: bool = True
    
    @model_validator(mode='after')
    def validate_overlap_less_than_size(self) -> Self:
        """P1 Fix: Ensure chunk_overlap < chunk_size"""
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )
        return self


class AlgorithmConfig(BaseModel):
    """Config for advanced algorithms (Raptor, GraphRAG)"""

    enable_raptor: bool = False
    raptor_max_cluster: int = 10
    enable_graphrag: bool = False
    graph_community_level: int = 2
    enable_mindmap: bool = False


class StrategyConfig(BaseModel):
    """
    策略配置 - 从UI注入
    
    P2 Fix: Supports both nested (chunking.mode) and flat (chunking_mode) access patterns.
    """

    # OCR/VLM策略
    ocr_provider: Literal["deepseek", "qwen-vl", "volc_engine", "paddle", "auto"] = "auto"
    ocr_fallback_chain: list[str] = Field(default_factory=lambda: ["qwen-vl", "volc_engine"])
    ocr_concurrency: int = 5
    force_ocr: bool = False
    
    # P1 Fix: Add scanned PDF detection option
    detect_complex_layout: bool = False

    # 分块策略 (nested)
    chunking: ChunkingStrategy = Field(default_factory=ChunkingStrategy)
    # 平铺访问（前端/配置可能传递）
    # P0 Fix: 添加字段验证确保 chunk_size > 0, chunk_overlap >= 0
    chunking_mode: Literal["fixed", "semantic", "layout_aware", "table_first"] | None = None
    chunk_size: int | None = Field(default=None, gt=0, description="Chunk size must be positive if set")
    chunk_overlap: int | None = Field(default=None, ge=0, description="Chunk overlap must be non-negative if set")
    preserve_tables: bool | None = None
    
    @model_validator(mode='after')
    def validate_flat_overlap_less_than_size(self) -> Self:
        """P1 Fix: Ensure flat chunk_overlap < chunk_size when both are set"""
        # Only validate if both flat fields are explicitly set
        if self.chunk_size is not None and self.chunk_overlap is not None:
            if self.chunk_overlap >= self.chunk_size:
                raise ValueError(
                    f"chunk_overlap ({self.chunk_overlap}) must be less than "
                    f"chunk_size ({self.chunk_size})"
                )
        return self

    # Embedding策略
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 64
    embedding_dimensions: int = 1024

    # 索引策略
    vector_backend: Literal["qdrant", "milvus", "auto"] = "auto"
    keyword_backend: Literal["elasticsearch", "disabled", "local"] = "elasticsearch"
    enable_quantization: bool = True  # Binary quantization for 100TB
    enable_hot_cold_tier: bool = False
    
    # 多模态索引
    enable_multimodal_index: bool = True

    # 算法增强 (New)
    algorithms: AlgorithmConfig = Field(default_factory=AlgorithmConfig)

    # 质量控制
    enable_cleaning: bool = False
    min_quality_score: float = 0.5
    enable_dedup: bool = True
    enable_pii_filter: bool = False
    
    # 语义缓存
    enable_semantic_cache: bool = False
    cache_ttl: int = 3600
    
    # 幻觉检测
    enable_hallucination_check: bool = False
    hallucination_threshold: float = 0.5

    # P2 Fix: Compatibility properties for flat field access
    @property
    def chunking_mode_effective(self) -> str:
        """平铺模式优先，否则回退 nested"""
        return self.chunking_mode or self.chunking.mode

    @property
    def chunk_size_effective(self) -> int:
        """平铺优先，否则回退"""
        return self.chunk_size if self.chunk_size is not None else self.chunking.chunk_size

    @property
    def chunk_overlap_effective(self) -> int:
        """平铺优先，否则回退 - P2 Fix: 0 is a valid value, use explicit None check"""
        return self.chunk_overlap if self.chunk_overlap is not None else self.chunking.chunk_overlap
    
    @property
    def preserve_tables_effective(self) -> bool:
        return self.preserve_tables if self.preserve_tables is not None else self.chunking.preserve_tables


# --- TypedDicts for LangGraph State ---


class ChunkMetadata(TypedDict):
    channel_id: str  # Multi-channel architecture
    doc_id: str
    batch_id: str
    page_num: int | None
    bbox: list[float] | None  # [x0, y0, x1, y1]
    block_type: Literal["text", "table", "image", "header", "footer"]
    media_type: str
    language: str
    quality_score: float
    ocr_provider: str | None
    ocr_confidence: float | None


class ProcessedChunk(TypedDict):
    id: str
    content: str
    page_num: int
    doc_id: str
    chunk_index: int
    metadata: ChunkMetadata


class IngestState(TypedDict):
    # Multi-channel 支持
    channel_id: str

    # 基础元数据
    task_id: str
    file_path: str
    file_type: str
    batch_id: str
    kb_name: str
    version: int

    # 策略配置 (Pydantic model dumped to dict)
    strategy_config: dict[str, Any]

    # 能力加载器 - 提供对已加载能力实例的访问
    # 类型为 Optional[Any] 以避免循环导入，实际类型为 CapabilityLoader
    capability_loader: Any | None

    # 管道数据
    raw_content: bytes | None
    extracted_text: str | None
    parsed_blocks: list[dict[str, Any]]  # [{"type": "text", "content": "...", "bbox": [...]}]
    images: list[dict[str, Any]]  # [{"data": bytes, "bbox": [...], "page": 1}]
    chunks: list[ProcessedChunk]
    vectors: list[list[float]]

    # 状态控制
    processing_stage: Literal["upload", "parse", "chunk", "embed", "index", "finalize"]
    retry_count: int
    error_log: list[dict[str, Any]]  # [{"stage": "parse", "error": "...", "timestamp": "..."}]
    progress: dict[str, Any]  # {"total_chunks": 100, "completed_chunks": 45}

    # 质量指标
    quality_metrics: dict[str, float]  # {"avg_quality": 0.85, "dedup_rate": 0.1}


class RetrievedChunk(ProcessedChunk):
    score: float
    rerank_score: float | None


class RetrievalState(TypedDict):
    # Multi-channel 支持
    channel_id: str
    session_id: str  # Chat session ID

    # 输入
    query_id: str
    input_query: str
    chat_history: list[dict[str, Any]]
    kb_names: list[str]  # Support multi-KB binding per session
    user_id: str

    # 策略配置
    strategy_config: dict[str, Any]  # {top_k, temperature, rerank_model, strict_mode}

    # 能力加载器 - 提供对已加载能力实例的访问
    capability_loader: Any | None

    # 中间态
    preprocessed_queries: list[str]  # Query decomposition/rewrite
    intent: dict[str, Any]  # {"type": "table_query", "filters": {"lang": "zh"}}

    # 检索结果
    vector_results: list[RetrievedChunk]  # Qdrant召回
    keyword_results: list[RetrievedChunk]  # ES召回
    fused_results: list[RetrievedChunk]  # RRF融合
    reranked_results: list[RetrievedChunk]  # Reranker排序
    retrieved_chunks: list[RetrievedChunk]  # Backward compatibility for existing code

    # 相关性判断
    relevance_score: float
    is_relevant: bool
    loop_count: int  # 防止死循环

    # 最终输出
    answer: str  # Backward compatibility
    final_answer: str
    citations: list[
        dict[str, Any]
    ]  # [{"doc_id": "...", "page": 3, "bbox": [...], "content": "..."}]
    confidence: float
    sources: list[dict[str, Any]]  # Backward compatibility


# --- Backward Compatibility Aliases ---
RAGState = RetrievalState
Source = dict[str, Any]
