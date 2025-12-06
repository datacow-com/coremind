# Embedding Configuration End-to-End Report

## 1. Architecture Overview
The embedding subsystem is now a fully integrated, end-to-end configurable component of OmniRAG.

### Backend (`server/api/models.py`)
- **API**: `GET /api/models/embedding` provides a curated list of supported models (BGE-M3, DashScope, OpenAI).
- **Health Check**: `POST /api/models/embedding/{id}/check` allows real-time latency verification of selected models using a dry-run embedding.

### Kernel (`core/embedding/provider_embedder.py`)
- **Async Native**: Implemented `httpx` based async calls for DashScope and thread-offloaded inference for local models.
- **Observability**: Integrated Prometheus metrics for `latency` and `error_rate`.
- **Resilience**: Fallback to simple hash embedding on failure ensures ingestion continuity.

### Frontend (`StrategyConfig.tsx`)
- **Dynamic Selection**: UI fetches model list from backend, displaying provider source.
- **Interactive Testing**: Users can click "Test" to verify model availability and latency before saving configuration.
- **Visual Feedback**: Latency (ms) and status (✓/✕) are displayed inline.

## 2. Flexibility & Usability
- **Custom Models**: Users can still input custom model IDs if not in the predefined list.
- **Provider Agnostic**: System seamlessly handles API keys (DashScope/OpenAI) vs Local Weights (HuggingFace).
- **Performance**: UI visualization of latency helps users choose between speed (DashScope/Local) and quality.

## 3. Conclusion
The embedding system meets the requirements for high-throughput, configurability, and observability. The closed-loop feedback from UI to Kernel ensures validity of configurations.

