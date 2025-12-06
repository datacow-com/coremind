from typing import Any

import numpy as np


class LocalIndex:
    def __init__(self, dim: int = 256):
        self.dim = dim
        self._vectors: list[Any] = []
        self._meta: list[dict[str, Any]] = []
        self._matrix: np.ndarray | None = None
        self._dirty: bool = False

    def add(self, vec: Any, meta: dict[str, Any]) -> None:
        try:
            d = getattr(vec, "shape", (self.dim,))[-1]
        except Exception:
            d = self.dim
        if d != self.dim:
            raise ValueError("vector dim mismatch")
        try:
            arr = np.asarray(vec, dtype=np.float32)
        except Exception:
            arr = np.array(vec, dtype=np.float32)
        self._vectors.append(arr)
        self._meta.append(meta)
        self._dirty = True

    def search(self, query_vec: Any, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self._vectors:
            return []
        if self._dirty or self._matrix is None:
            self._matrix = np.stack(self._vectors, axis=0)
            self._dirty = False
        mat = self._matrix  # (N, D)
        # cosine similarity
        q = query_vec
        if not isinstance(q, np.ndarray):
            q = np.array(q, dtype=np.float32)
        else:
            q = q.astype(np.float32)
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            scores = mat @ q
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

    def list_all_meta(self) -> list[dict[str, Any]]:
        return list(self._meta)

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
