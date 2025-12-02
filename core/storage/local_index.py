from typing import Any

import numpy as np


class LocalIndex:
    def __init__(self, dim: int = 256):
        self.dim = dim
        self._vectors: list[np.ndarray] = []
        self._meta: list[dict[str, Any]] = []

    def add(self, vec: np.ndarray, meta: dict[str, Any]) -> None:
        if vec.shape[-1] != self.dim:
            raise ValueError("vector dim mismatch")
        self._vectors.append(vec.astype(np.float32))
        self._meta.append(meta)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self._vectors:
            return []
        mat = np.stack(self._vectors, axis=0)  # (N, D)
        # cosine similarity
        q = query_vec.astype(np.float32)
        scores = mat @ q  # since both are l2-normalized
        idx = np.argsort(-scores)[:top_k]
        return [(self._meta[i], float(scores[i])) for i in idx]

    def list_page_meta(self, doc_id: str, page_num: int) -> list[dict[str, Any]]:
        res: list[dict[str, Any]] = []
        for m in self._meta:
            if m.get("doc_id") == doc_id and int(m.get("page_num") or 0) == int(page_num):
                res.append(m)
        return res

    def doc_stats(self, doc_id: str) -> dict[str, Any]:
        cnt = 0
        pages = set()
        for m in self._meta:
            if m.get("doc_id") == doc_id:
                cnt += 1
                pn = int(m.get("page_num") or 0)
                if pn > 0:
                    pages.add(pn)
        return {"chunk_count": cnt, "processed_pages": len(pages)}

    def stats_all(self) -> dict[str, Any]:
        docs = set()
        for m in self._meta:
            did = m.get("doc_id")
            if did:
                docs.add(did)
        return {
            "document_count": len(docs),
            "chunk_count": len(self._meta),
            "embedding_dimension": self.dim,
        }

    def delete_document(self, doc_id: str) -> int:
        if not self._meta:
            return 0
        new_vecs = []
        new_meta = []
        removed = 0
        for v, m in zip(self._vectors, self._meta, strict=False):
            if m.get("doc_id") == doc_id:
                removed += 1
                continue
            new_vecs.append(v)
            new_meta.append(m)
        self._vectors = new_vecs
        self._meta = new_meta
        return removed


_INDEX = LocalIndex()


def get_index() -> LocalIndex:
    return _INDEX
