from typing import List
from langchain_core.retrievers import BaseRetriever


class OmniIndexRetriever(BaseRetriever):
    def __init__(self, top_k: int = 5):
        super().__init__()
        self.top_k = top_k

    def _get_relevant_documents(self, query: str) -> List:
        from core.embedding.provider_embedder import Embedder
        from core.storage.index_router import search as index_search
        emb = Embedder(dim=256)
        qvec = emb.embed(query)
        results = index_search(qvec, top_k=self.top_k) or []
        # Convert to LangChain-like Document objects (lazy minimal wrapper)
        class Doc:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata
        out: List[Doc] = []
        for meta, score in results:
            out.append(Doc(page_content=meta.get("content"), metadata={"score": float(score), **meta}))
        return out

