import logging
import os
import warnings
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

# Mark as deprecated
warnings.warn("core.ingestion.graph_ingest is deprecated. Use core.ingestion.graph instead.", DeprecationWarning, stacklevel=2)

# Re-export new graph if possible, or keep legacy logic as fallback wrapper
# Since TypedDict names conflict (IngestState), we keep legacy definition but warn users.
# This file was used for PDF ingestion via VLM.
# The new pipeline handles PDF via Router -> CpuParser or GpuParser.

class LegacyIngestState(TypedDict):
    file_path: str
    images: list[str]
    md: str | None
    meta: dict[str, Any]

# ... (Legacy functions kept for compatibility but warned) ...

def create_ingest_graph():
    # Redirect to new graph?
    # The new graph uses 'core.state.IngestState', which is superset of LegacyIngestState?
    # Legacy: {file_path, images, md, meta}
    # New: {task_id, file_path, file_type, ... parsed_blocks, chunks, ...}
    # They are not compatible. We must keep this legacy graph logic or migrate callers.
    # Callers: core/pipeline/builder.py (updated to use new graph for PDF), server/routes.py (updated).
    # So this file should not be called anymore for new flows.
    # We leave it as is for safety but marked deprecated.
    
    from core.ingestion.graph_ingest_legacy import create_ingest_graph as legacy_create
    return legacy_create()

# We will rename the content of this file to graph_ingest_legacy.py and make this file a proxy or just keep it.
# Actually, since we updated builder.py, this file is effectively orphaned or used only if `use_new_pipeline=False`.
# We should keep it functioning for legacy rollback.

pass

