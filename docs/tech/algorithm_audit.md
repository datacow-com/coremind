# Algorithm Implementation Audit Report

## 1. GraphRAG (Deep/Light)
- **Status**: Static / Mock / Low Efficiency
- **Issues**:
    - `graphrag_light.py`: `collect_chunks` is static (returns `list_all_meta()` without filtering by KB). 
    - `graphrag_deep.py`: `extract_graph` uses naive LLM extraction ("return JSON") without schema enforcement or chunking strategy. Error handling is broad (`except Exception: data = {}`).
    - Concurrency is limited by `asyncio.Semaphore` but uses `LLMGateway` which might not be optimized for high throughput graph extraction.
    - No graph partitioning or community detection (Leiden) implemented, which is core to GraphRAG.
    - **Recommendation**: Rewrite `collect_chunks` to use Qdrant scrolling. Implement community detection. Use structured output parsing for extraction.

## 2. Raptor (Deep/Light)
- **Status**: Experimental / Redundant
- **Issues**:
    - `raptor_light.py` & `raptor_deep.py`: Duplicate logic for clustering (`_cluster` vs `random.shuffle` in light).
    - `collect_chunks` loads **ALL** chunks into memory via `list_all_meta()`. This will OOM at 100TB scale.
    - Clustering is K-Means on client-side (numpy/scikit not explicitly used, implementation looks like naive K-Means).
    - **Recommendation**: Use Qdrant's grouping/clustering or Scikit-learn for clustering. Paginate chunk loading. Unify Light/Deep into a single parameterized graph.

## 3. Mindmap Light
- **Status**: Mock / Placeholder
- **Issues**:
    - Naive iteration over documents.
    - Generates "outline" by summarizing first 50 chunks of each doc.
    - No true hierarchical "Mindmap" generation (just a list of doc summaries).
    - **Recommendation**: Implement true recursive summarization or topic modeling.

## 4. General Issues
- **Memory Unsafe**: All algorithms use `list_all_meta()` which likely loads the entire index into RAM.
- **Lack of Async Persistence**: Graphs store results to local JSON files (`store_graph`, `store_raptor`), ignoring the `BlobStorage` abstraction or Database.
- **No Error Recovery**: Failed extraction results in empty data, no partial checkpointing beyond LangGraph's default (which might be too coarse).

## Refactoring Plan
1.  **Unified Data Loader**: Create `GraphLoaderNode` that streams chunks from Qdrant/ES using cursor/scroll.
2.  **Raptor Unification**: Merge Light/Deep into `RaptorGraph`. Use `sklearn.cluster.MiniBatchKMeans`.
3.  **GraphRAG Upgrade**: Implement Leiden algorithm for community detection. Use `GraphStore` (e.g., NetworkX -> JSON/Neo4j) abstraction.
4.  **Storage Abstraction**: Replace `os.path.join` / `open()` with `BlobStorage.put()`.

