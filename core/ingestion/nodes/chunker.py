"""
Smart Chunker - Intelligent document chunking with multiple strategies.

Supports:
- fixed: Classic RecursiveCharacterTextSplitter
- table_first: Separate tables as standalone chunks, then split text
- layout_aware: Respect document layout, tables/images as boundaries
- semantic: Use sentence embeddings for semantic similarity-based chunking
- heading_based: Split by headings/sections, preserving document structure
"""

import re
from typing import Any

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from core.state import IngestState, ProcessedChunk
from core.utils.monitor import ingest_duration

# Optional: Language detection
try:
    from langdetect import detect as detect_language
    from langdetect.lang_detect_exception import LangDetectException

    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False


class SmartChunker:
    """Smart document chunker with multiple strategies."""

    # Heading patterns for structure detection
    HEADING_PATTERNS = [
        (r"^#{1,6}\s+.+$", "markdown"),  # Markdown headings
        (r"^第[一二三四五六七八九十\d]+[章节条款]", "chinese_legal"),  # Chinese legal structure
        (r"^\d+\.\s+.+$", "numbered"),  # Numbered sections
        (r"^[A-Z][A-Z\s]+$", "caps"),  # ALL CAPS headings
    ]

    def __init__(self):
        self._language_cache: dict[str, str] = {}

    async def __call__(self, state: IngestState) -> IngestState:
        with ingest_duration.labels(stage="chunker").time():
            cfg = state["strategy_config"]
            chunk_cfg = cfg.get("chunking", {})
            if hasattr(chunk_cfg, "dict"):
                chunk_cfg = chunk_cfg.dict()

            mode = chunk_cfg.get("mode", "fixed")
            chunk_size = chunk_cfg.get("chunk_size", 512)
            chunk_overlap = chunk_cfg.get("chunk_overlap", 50)

            parsed_blocks = state["parsed_blocks"]
            chunks: list[ProcessedChunk] = []
            idx = 0

            # Dispatch to appropriate chunking strategy
            if mode == "table_first":
                chunks, idx = self._chunk_table_first(
                    state, parsed_blocks, chunk_size, chunk_overlap
                )
            elif mode == "layout_aware":
                chunks, idx = self._chunk_layout_aware(
                    state, parsed_blocks, chunk_size
                )
            elif mode == "semantic":
                chunks, idx = await self._chunk_semantic(
                    state, parsed_blocks, chunk_size, chunk_overlap
                )
            elif mode == "heading_based":
                chunks, idx = self._chunk_heading_based(
                    state, parsed_blocks, chunk_size, chunk_overlap
                )
            else:  # Fixed (Default)
                chunks, idx = self._chunk_fixed(
                    state, parsed_blocks, chunk_size, chunk_overlap
                )

            state["chunks"] = chunks
            state["processing_stage"] = "embed"
            if "progress" not in state:
                state["progress"] = {}
            state["progress"]["total_chunks"] = len(chunks)

            return state

    def _detect_language(self, text: str) -> str:
        """Detect language of text content."""
        if not LANGDETECT_AVAILABLE or not text or len(text.strip()) < 20:
            return "unknown"

        # Check cache first
        cache_key = text[:100]  # Use first 100 chars as key
        if cache_key in self._language_cache:
            return self._language_cache[cache_key]

        try:
            lang = detect_language(text)
            self._language_cache[cache_key] = lang
            return lang
        except LangDetectException:
            return "unknown"

    def _detect_heading_level(self, text: str) -> int | None:
        """Detect heading level from text."""
        if not text:
            return None

        # Markdown style
        match = re.match(r"^(#{1,6})\s+", text)
        if match:
            return len(match.group(1))

        # Chinese legal style
        if re.match(r"^第[一二三四五六七八九十\d]+章", text):
            return 1
        if re.match(r"^第[一二三四五六七八九十\d]+节", text):
            return 2
        if re.match(r"^第[一二三四五六七八九十\d]+条", text):
            return 3

        # Numbered style
        match = re.match(r"^(\d+(?:\.\d+)*)\.\s+", text)
        if match:
            parts = match.group(1).split(".")
            return min(len(parts), 6)

        return None

    def _calculate_weights(
        self, block_type: str, page_num: int, heading_level: int | None
    ) -> dict[str, float]:
        """Calculate relevance weights for ranking."""
        weights = {
            "type_weight": 1.0,
            "position_weight": 1.0,
            "heading_weight": 1.0,
        }

        # Type weight: tables and headings are often more important
        type_weights = {
            "table": 1.5,
            "header": 1.3,
            "heading": 1.2,
            "text": 1.0,
            "image": 0.8,
            "footer": 0.5,
        }
        weights["type_weight"] = type_weights.get(block_type, 1.0)

        # Position weight: content near the beginning is often more important
        if page_num > 0:
            weights["position_weight"] = 1.0 / (1.0 + 0.05 * page_num)

        # Heading weight: higher-level headings are more important
        if heading_level:
            weights["heading_weight"] = 1.0 + 0.1 * (7 - heading_level)

        return weights

    def _create_chunk(
        self,
        state: IngestState,
        content: str,
        idx: int,
        block_type: str,
        source_block: dict[str, Any] | None = None,
        section_title: str | None = None,
    ) -> ProcessedChunk:
        """Create a chunk with enhanced metadata."""
        page_num = source_block.get("page", 0) if source_block else 0
        heading_level = (
            source_block.get("heading_level")
            if source_block
            else self._detect_heading_level(content)
        )

        # Calculate weights
        weights = self._calculate_weights(block_type, page_num, heading_level)

        # Detect language
        language = self._detect_language(content)

        meta = {
            # Required fields
            "channel_id": state.get("channel_id", ""),
            "doc_id": state["task_id"],
            "batch_id": state["batch_id"],
            "block_type": block_type,
            "media_type": state["file_type"],
            "page_num": page_num,
            "bbox": source_block.get("bbox") if source_block else None,
            # Quality & OCR
            "language": language,
            "quality_score": source_block.get("quality_score", 1.0) if source_block else 1.0,
            "ocr_provider": source_block.get("ocr_provider") if source_block else None,
            "ocr_confidence": source_block.get("ocr_confidence") if source_block else None,
            # Structure metadata (NEW)
            "heading_level": heading_level,
            "section_title": section_title or source_block.get("section_title") if source_block else None,
            # Weights for ranking (NEW)
            "type_weight": weights["type_weight"],
            "position_weight": weights["position_weight"],
            "heading_weight": weights["heading_weight"],
        }

        import uuid
        
        # Generate UUID for Qdrant compatibility (requires UUID or unsigned int)
        chunk_uuid = str(uuid.uuid4())
        
        return {
            "id": chunk_uuid,
            "content": content,
            "page_num": page_num,
            "doc_id": state["task_id"],
            "chunk_index": idx,
            "metadata": meta,
        }

    def _chunk_fixed(
        self,
        state: IngestState,
        parsed_blocks: list[dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[list[ProcessedChunk], int]:
        """Classic fixed-size chunking with RecursiveCharacterTextSplitter."""
        chunks = []
        idx = 0

        full_text = "\n".join([b.get("content", "") for b in parsed_blocks])
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        texts = splitter.split_text(full_text)

        for text in texts:
            chunks.append(self._create_chunk(state, text, idx, "text"))
            idx += 1

        return chunks, idx

    def _chunk_table_first(
        self,
        state: IngestState,
        parsed_blocks: list[dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[list[ProcessedChunk], int]:
        """Separate tables as standalone chunks, then split remaining text."""
        chunks = []
        idx = 0

        table_blocks = [b for b in parsed_blocks if b.get("type") == "table"]
        text_blocks = [b for b in parsed_blocks if b.get("type") != "table"]

        # 1. Process Tables (Standalone chunks with high weight)
        for tb in table_blocks:
            content = tb.get("content", "")
            chunks.append(
                self._create_chunk(state, content, idx, "table", source_block=tb)
            )
            idx += 1

        # 2. Process Text (Fixed splitting)
        full_text = "\n".join([b.get("content", "") for b in text_blocks])
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        texts = splitter.split_text(full_text)

        for text in texts:
            chunks.append(self._create_chunk(state, text, idx, "text"))
            idx += 1

        return chunks, idx

    def _chunk_layout_aware(
        self,
        state: IngestState,
        parsed_blocks: list[dict[str, Any]],
        chunk_size: int,
    ) -> tuple[list[ProcessedChunk], int]:
        """Respect document layout, using tables/images as chunk boundaries."""
        chunks = []
        idx = 0
        current_chunk = ""
        current_page = 0

        for block in parsed_blocks:
            b_type = block.get("type", "text")
            content = block.get("content", "")
            if not content:
                continue

            # Tables/images are standalone chunks - flush current and add
            if b_type in ["image", "table"]:
                if current_chunk:
                    chunks.append(
                        self._create_chunk(state, current_chunk.strip(), idx, "text")
                    )
                    idx += 1
                    current_chunk = ""
                chunks.append(
                    self._create_chunk(state, content, idx, b_type, source_block=block)
                )
                idx += 1
                continue

            # Accumulate text, split when exceeding chunk_size
            if len(current_chunk) + len(content) > chunk_size:
                if current_chunk:
                    chunks.append(
                        self._create_chunk(state, current_chunk.strip(), idx, "text")
                    )
                    idx += 1
                current_chunk = content
            else:
                if current_chunk:
                    current_chunk += "\n"
                current_chunk += content

            current_page = block.get("page", current_page)

        # Flush remaining content
        if current_chunk:
            chunks.append(
                self._create_chunk(state, current_chunk.strip(), idx, "text")
            )
            idx += 1

        return chunks, idx

    async def _chunk_semantic(
        self,
        state: IngestState,
        parsed_blocks: list[dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[list[ProcessedChunk], int]:
        """
        Semantic chunking: split by sentence similarity.
        Falls back to fixed chunking if embeddings unavailable.
        """
        chunks = []
        idx = 0

        # Collect all text content
        full_text = "\n".join([b.get("content", "") for b in parsed_blocks])

        # Split into sentences first
        sentences = self._split_into_sentences(full_text)
        if len(sentences) <= 1:
            # Too short, use fixed chunking
            return self._chunk_fixed(state, parsed_blocks, chunk_size, chunk_overlap)

        try:
            # Try to get embedder from capability loader
            capability_loader = state.get("capability_loader")
            embedder = None
            if capability_loader:
                embedder = capability_loader.get("multimodal_embedding")

            if not embedder:
                # Fallback to fixed chunking
                return self._chunk_fixed(state, parsed_blocks, chunk_size, chunk_overlap)

            # Generate embeddings for sentences
            embeddings = []
            for sent in sentences:
                emb = await embedder.embed_text(sent)
                embeddings.append(emb)

            # Group sentences by similarity using breakpoint detection
            groups = self._group_by_similarity(sentences, embeddings, threshold=0.7)

            for group in groups:
                content = " ".join(group)
                # If group is too large, split further
                if len(content) > chunk_size * 2:
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap
                    )
                    for sub_text in splitter.split_text(content):
                        chunks.append(self._create_chunk(state, sub_text, idx, "text"))
                        idx += 1
                else:
                    chunks.append(self._create_chunk(state, content, idx, "text"))
                    idx += 1

        except Exception:
            # Fallback to fixed chunking on any error
            return self._chunk_fixed(state, parsed_blocks, chunk_size, chunk_overlap)

        return chunks, idx

    def _chunk_heading_based(
        self,
        state: IngestState,
        parsed_blocks: list[dict[str, Any]],
        chunk_size: int,
        chunk_overlap: int,
    ) -> tuple[list[ProcessedChunk], int]:
        """Split by headings/sections, preserving document structure."""
        chunks = []
        idx = 0

        current_section = ""
        current_section_title = None
        current_heading_level = None

        for block in parsed_blocks:
            b_type = block.get("type", "text")
            content = block.get("content", "")
            if not content:
                continue

            # Tables/images as standalone
            if b_type in ["image", "table"]:
                if current_section:
                    chunks.append(
                        self._create_chunk(
                            state,
                            current_section.strip(),
                            idx,
                            "text",
                            section_title=current_section_title,
                        )
                    )
                    idx += 1
                    current_section = ""
                chunks.append(
                    self._create_chunk(state, content, idx, b_type, source_block=block)
                )
                idx += 1
                continue

            # Check if this is a heading
            heading_level = self._detect_heading_level(content)
            is_heading = heading_level is not None or b_type in ["header", "heading"]

            if is_heading:
                # Flush previous section
                if current_section:
                    chunks.append(
                        self._create_chunk(
                            state,
                            current_section.strip(),
                            idx,
                            "text",
                            section_title=current_section_title,
                        )
                    )
                    idx += 1

                # Start new section
                current_section = content
                current_section_title = content.strip()[:100]
                current_heading_level = heading_level
            else:
                # Accumulate text in current section
                if current_section:
                    current_section += "\n"
                current_section += content

                # Split if too large
                if len(current_section) > chunk_size * 1.5:
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap
                    )
                    texts = splitter.split_text(current_section)
                    for i, text in enumerate(texts[:-1]):
                        chunks.append(
                            self._create_chunk(
                                state,
                                text.strip(),
                                idx,
                                "text",
                                section_title=current_section_title,
                            )
                        )
                        idx += 1
                    current_section = texts[-1] if texts else ""

        # Flush remaining
        if current_section.strip():
            chunks.append(
                self._create_chunk(
                    state,
                    current_section.strip(),
                    idx,
                    "text",
                    section_title=current_section_title,
                )
            )
            idx += 1

        return chunks, idx

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences for semantic chunking."""
        # Simple sentence splitter - handles Chinese and English
        # Chinese: split on 。！？
        # English: split on . ! ?
        pattern = r"(?<=[。！？.!?])\s*"
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_by_similarity(
        self, sentences: list[str], embeddings: list[list[float]], threshold: float
    ) -> list[list[str]]:
        """Group sentences by embedding similarity."""
        import numpy as np

        if len(sentences) <= 1:
            return [sentences]

        groups = []
        current_group = [sentences[0]]

        for i in range(1, len(sentences)):
            # Calculate cosine similarity with previous sentence
            prev_emb = np.array(embeddings[i - 1])
            curr_emb = np.array(embeddings[i])

            similarity = np.dot(prev_emb, curr_emb) / (
                np.linalg.norm(prev_emb) * np.linalg.norm(curr_emb) + 1e-8
            )

            if similarity >= threshold:
                # Similar, add to current group
                current_group.append(sentences[i])
            else:
                # Breakpoint - start new group
                groups.append(current_group)
                current_group = [sentences[i]]

        # Add last group
        if current_group:
            groups.append(current_group)

        return groups
