from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# --- Pydantic Models for API / Strategy Config ---

class ChunkingStrategy(BaseModel):
    mode: Literal["fixed", "semantic", "layout_aware", "table_first"] = "fixed"
    chunk_size: int = 512
    chunk_overlap: int = 50
    preserve_tables: bool = True

class AlgorithmConfig(BaseModel):
    """Config for advanced algorithms (Raptor, GraphRAG)"""
    enable_raptor: bool = False
    raptor_max_cluster: int = 10
    enable_graphrag: bool = False
    graph_community_level: int = 2
    enable_mindmap: bool = False

class StrategyConfig(BaseModel):
    """策略配置 - 从UI注入"""
    # OCR/VLM策略
    ocr_provider: Literal["deepseek", "qwen-vl", "volc_engine", "paddle", "auto"] = "auto"
    ocr_fallback_chain: List[str] = Field(default_factory=lambda: ["qwen-vl", "volc_engine"])
    ocr_concurrency: int = 5
    force_ocr: bool = False
    
    # 分块策略
    chunking: ChunkingStrategy = Field(default_factory=ChunkingStrategy)
    
    # Embedding策略
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 64
    embedding_dimensions: int = 1024
    
    # 索引策略
    vector_backend: Literal["qdrant", "milvus", "auto"] = "auto"
    keyword_backend: Literal["elasticsearch", "disabled", "local"] = "elasticsearch"
    enable_quantization: bool = True  # Binary quantization for 100TB
    enable_hot_cold_tier: bool = False
    
    # 算法增强 (New)
    algorithms: AlgorithmConfig = Field(default_factory=AlgorithmConfig)
    
    # 质量控制
    enable_cleaning: bool = False
    min_quality_score: float = 0.5
    enable_dedup: bool = True
    enable_pii_filter: bool = False

# --- TypedDicts for LangGraph State ---

class ChunkMetadata(TypedDict):
    doc_id: str
    batch_id: str
    page_num: Optional[int]
    bbox: Optional[List[float]]  # [x0, y0, x1, y1]
    block_type: Literal["text", "table", "image", "header", "footer"]
    media_type: str
    language: str
    quality_score: float
    ocr_provider: Optional[str]
    ocr_confidence: Optional[float]

class ProcessedChunk(TypedDict):
    id: str
    content: str
    page_num: int
    doc_id: str
    chunk_index: int
    metadata: ChunkMetadata

class IngestState(TypedDict):
    # 基础元数据
    task_id: str
    file_path: str
    file_type: str
    batch_id: str
    kb_name: str
    version: int
    
    # 策略配置 (Pydantic model dumped to dict)
    strategy_config: Dict[str, Any]
    
    # 管道数据
    raw_content: Optional[bytes]
    extracted_text: Optional[str]
    parsed_blocks: List[Dict[str, Any]]  # [{"type": "text", "content": "...", "bbox": [...]}]
    images: List[Dict[str, Any]]  # [{"data": bytes, "bbox": [...], "page": 1}]
    chunks: List[ProcessedChunk]
    vectors: List[List[float]]
    
    # 状态控制
    processing_stage: Literal["upload", "parse", "chunk", "embed", "index", "finalize"]
    retry_count: int
    error_log: List[Dict[str, Any]]  # [{"stage": "parse", "error": "...", "timestamp": "..."}]
    progress: Dict[str, Any]  # {"total_chunks": 100, "completed_chunks": 45}
    
    # 质量指标
    quality_metrics: Dict[str, float]  # {"avg_quality": 0.85, "dedup_rate": 0.1}

class RetrievedChunk(ProcessedChunk):
    score: float
    rerank_score: Optional[float]

class RetrievalState(TypedDict):
    # 输入
    query_id: str
    input_query: str
    chat_history: List[Dict[str, Any]]
    kb_name: str
    user_id: str
    
    # 策略配置
    strategy_config: Dict[str, Any]  # {top_k, temperature, rerank_model, strict_mode}
    
    # 中间态
    preprocessed_queries: List[str]  # Query decomposition/rewrite
    intent: Dict[str, Any]  # {"type": "table_query", "filters": {"lang": "zh"}}
    
    # 检索结果
    vector_results: List[RetrievedChunk]  # Qdrant召回
    keyword_results: List[RetrievedChunk]  # ES召回
    fused_results: List[RetrievedChunk]  # RRF融合
    reranked_results: List[RetrievedChunk]  # Reranker排序
    retrieved_chunks: List[RetrievedChunk] # Backward compatibility for existing code
    
    # 相关性判断
    relevance_score: float
    is_relevant: bool
    loop_count: int  # 防止死循环
    
    # 最终输出
    answer: str # Backward compatibility
    final_answer: str
    citations: List[Dict[str, Any]]  # [{"doc_id": "...", "page": 3, "bbox": [...], "content": "..."}]
    confidence: float
    sources: List[Dict[str, Any]] # Backward compatibility

# --- Backward Compatibility Aliases ---
RAGState = RetrievalState
