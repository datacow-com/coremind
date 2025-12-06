from typing import Any

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever


class OmniIndexRetriever(BaseRetriever):
    top_k: int = 5

    def _get_relevant_documents(self, query: str, *, run_manager: Any = None) -> list[Document]:
        from core.embedding.provider_embedder import Embedder
        from core.storage.index_router import search as index_search

        emb = Embedder(dim=256)
        qvec = emb.embed(query)
        results = index_search(qvec, top_k=int(getattr(self, "top_k", 5))) or []
        out: list[Document] = []
        for meta, score in results:
            out.append(
                Document(page_content=meta.get("content"), metadata={"score": float(score), **meta})
            )
        return out
