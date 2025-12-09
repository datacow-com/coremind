try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from core.state import IngestState, ProcessedChunk
from core.utils.monitor import ingest_duration


class SmartChunker:
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

            if mode == "table_first":
                # Separate tables and non-tables
                table_blocks = [b for b in parsed_blocks if b.get("type") == "table"]
                text_blocks = [b for b in parsed_blocks if b.get("type") != "table"]

                # 1. Process Tables (Standalone chunks)
                for tb in table_blocks:
                    content = tb.get("content", "")
                    # Optional: Summarize table using LLM here or in separate node
                    # For now, just use content (markdown)

                    chunks.append(
                        {
                            "id": f"{state['task_id']}_{idx}",
                            "content": content,
                            "page_num": tb.get("page", 0),
                            "doc_id": state["task_id"],
                            "chunk_index": idx,
                            "metadata": {
                                "doc_id": state["task_id"],
                                "batch_id": state["batch_id"],
                                "block_type": "table",
                                "media_type": state["file_type"],
                                "language": "unknown",
                                "quality_score": 1.0,
                                "ocr_provider": tb.get("ocr_provider"),
                                "ocr_confidence": tb.get("ocr_confidence"),
                                "page_num": tb.get("page", 0),
                                "bbox": tb.get("bbox"),
                            },
                        }
                    )
                    idx += 1

                # 2. Process Text (Fixed splitting)
                full_text = "\n".join([b.get("content", "") for b in text_blocks])
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )
                texts = splitter.split_text(full_text)

                for text in texts:
                    chunks.append(
                        {
                            "id": f"{state['task_id']}_{idx}",
                            "content": text,
                            "page_num": 0,  # Lossy page mapping for aggregated text
                            "doc_id": state["task_id"],
                            "chunk_index": idx,
                            "metadata": {
                                "doc_id": state["task_id"],
                                "batch_id": state["batch_id"],
                                "block_type": "text",
                                "media_type": state["file_type"],
                                "language": "unknown",
                                "quality_score": 1.0,
                                "ocr_provider": None,
                                "ocr_confidence": None,
                                "page_num": 0,
                                "bbox": None,
                            },
                        }
                    )
                    idx += 1

            elif mode == "layout_aware":
                current_chunk = ""
                for block in parsed_blocks:
                    b_type = block.get("type", "text")
                    content = block.get("content", "")
                    if not content:
                        continue

                    # 表格/图片独立成块，并在前后断开上下文
                    if b_type in ["image", "table"]:
                        if current_chunk:
                            chunks.append(
                                self._create_chunk(state, current_chunk.strip(), idx, "text")
                            )
                            idx += 1
                            current_chunk = ""
                        chunks.append(self._create_chunk(state, content, idx, b_type, block))
                        idx += 1
                        continue

                    # 文本按布局顺序累积，超过阈值则切块
                    if len(current_chunk) + len(content) > chunk_size:
                        chunks.append(self._create_chunk(state, current_chunk.strip(), idx, "text"))
                        idx += 1
                        current_chunk = content
                    else:
                        if current_chunk:
                            current_chunk += "\n"
                        current_chunk += content

                if current_chunk:
                    chunks.append(self._create_chunk(state, current_chunk.strip(), idx, "text"))
                    idx += 1

            else:  # Fixed (Default)
                full_text = "\n".join([b.get("content", "") for b in parsed_blocks])
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )
                texts = splitter.split_text(full_text)
                for text in texts:
                    chunks.append(self._create_chunk(state, text, idx, "text"))
                    idx += 1

            state["chunks"] = chunks
            state["processing_stage"] = "embed"
            if "progress" not in state:
                state["progress"] = {}
            state["progress"]["total_chunks"] = len(chunks)

            return state

    def _create_chunk(self, state, content, idx, block_type, source_block=None):
        meta = {
            "doc_id": state["task_id"],
            "batch_id": state["batch_id"],
            "block_type": block_type,
            "media_type": state["file_type"],
            "language": "unknown",
            "quality_score": 1.0,
            "ocr_provider": source_block.get("ocr_provider") if source_block else None,
            "ocr_confidence": source_block.get("ocr_confidence") if source_block else None,
            "page_num": source_block.get("page", 0) if source_block else 0,
            "bbox": source_block.get("bbox") if source_block else None,
        }
        return {
            "id": f"{state['task_id']}_{idx}",
            "content": content,
            "page_num": meta["page_num"],
            "doc_id": state["task_id"],
            "chunk_index": idx,
            "metadata": meta,
        }
