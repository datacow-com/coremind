# Hybrid Retrieval & Rerank Logic

## 1. Dual-Path Retrieval

为了解决“专有名词查不到”的问题，必须同时并行两路检索：

- **Path A: Dense Vector Search (Milvus)**
  - Embedding Model: `bge-m3` or `text-embedding-004`.
  - Metric: Cosine Similarity.
  - Top_K: 100.

- **Path B: Sparse/Keyword Search (BM25)**
  - Implementation: Use Milvus 2.4+ Sparse Vector support OR separate BM25 index.
  - Tokenizer: Jieba (Chinese) / Tiktoken (English).
  - Top_K: 100.

## 2. Reciprocal Rank Fusion (RRF)

将两路结果进行融合：
$$ Score(d) = \sum*{path \in \{A, B\}} \frac{1}{k + rank*{path}(d)} $$
其中 $k=60$。

## 3. Reranking (Crucial)

取 RRF 融合后的 Top-50 文档，调用 Rerank 模型 (BGE-Reranker-v2)。

- **Input**: (User Query, Document Text).
- **Output**: Similarity Score.
- **Filter**: 丢弃 Score < 0.2 的结果。
- **Final Context**: 取 Top-8 喂给 LLM。
