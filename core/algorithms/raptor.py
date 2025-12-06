import asyncio
import json
import numpy as np
from typing import List, Dict, Any
from sklearn.cluster import MiniBatchKMeans
from core.storage.vector_store import get_vector_client
from core.storage.blob_store import get_blob_store
from core.embedding.registry import get_embedder
from core.llm.gateway import LLMGateway

class RaptorProcessor:
    def __init__(self, kb_name: str, config: Dict[str, Any] = None):
        self.kb_name = kb_name
        self.config = config or {}
        self.vector_store = get_vector_client()
        self.blob_store = get_blob_store()
        
        # Use configured models or defaults from DB/Env
        llm_model = self.config.get("llm_model") # Optional override
        embedding_model = self.config.get("embedding_model") # Optional override
        
        self.llm = LLMGateway(model=llm_model)
        self.embedder = get_embedder(model_name=embedding_model)

    async def process(self, max_clusters: int = 10):
        collection_name = f"kb_{self.kb_name}_v1"
        
        # 1. Fetch Data (Streaming)
        texts = []
        # For real implementation, we should fetch vectors if available to save embedding cost
        # Assuming Qdrant has vectors.
        
        offset = None
        # Limit sample size for clustering to avoid OOM
        MAX_SAMPLE = 10000 
        
        fetched_count = 0
        while fetched_count < MAX_SAMPLE:
            points, offset = await self.vector_store.scroll(collection_name, limit=1000, offset_id=offset)
            if not points:
                break
            
            batch_texts = [p['content'] for p in points if p['content']]
            texts.extend(batch_texts)
            fetched_count += len(batch_texts)
            
            if offset is None:
                break
        
        if not texts:
            return

        # 2. Embed (if vectors not retrieved)
        # In production, we should retrieve vectors from Qdrant to avoid re-embedding
        # For this skeleton, we re-embed for simplicity using the new Embedder
        embeddings = await self.embedder.embed_batch(texts)
        
        # 3. Clustering
        n_clusters = min(max_clusters, len(texts))
        if n_clusters < 2:
            return

        kmeans = MiniBatchKMeans(n_clusters=n_clusters, batch_size=256, n_init=10)
        kmeans.fit(embeddings)
        labels = kmeans.labels_
        
        # 4. Summarize Clusters
        clusters: Dict[int, List[str]] = {}
        for i, label in enumerate(labels):
            clusters.setdefault(label, []).append(texts[i])
            
        summaries = {}
        for label, cluster_texts in clusters.items():
            # Summarize context
            context = "\n".join(cluster_texts[:10]) # Limit context window
            prompt = "Summarize the following related text segments into a single coherent paragraph."
            summary = await self.llm.chat(prompt, context=context)
            summaries[int(label)] = summary
            
        # 5. Store Result
        result = {
            "clusters": {k: v[:5] for k, v in clusters.items()}, # Store samples
            "summaries": summaries
        }
        await self.blob_store.put(f"raptor/{self.kb_name}.json", json.dumps(result).encode('utf-8'))
