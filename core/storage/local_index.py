from typing import Dict, Any, List, Tuple
import numpy as np


class LocalIndex:
    def __init__(self, dim: int = 256):
        self.dim = dim
        self._vectors: List[np.ndarray] = []
        self._meta: List[Dict[str, Any]] = []

    def add(self, vec: np.ndarray, meta: Dict[str, Any]) -> None:
        if vec.shape[-1] != self.dim:
            raise ValueError("vector dim mismatch")
        self._vectors.append(vec.astype(np.float32))
        self._meta.append(meta)

    def search(self, query_vec: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not self._vectors:
            return []
        mat = np.stack(self._vectors, axis=0)  # (N, D)
        # cosine similarity
        q = query_vec.astype(np.float32)
        scores = mat @ q  # since both are l2-normalized
        idx = np.argsort(-scores)[:top_k]
        return [(self._meta[i], float(scores[i])) for i in idx]

    def list_page_meta(self, doc_id: str, page_num: int) -> List[Dict[str, Any]]:
        res: List[Dict[str, Any]] = []
        for m in self._meta:
            if m.get("doc_id") == doc_id and int(m.get("page_num") or 0) == int(page_num):
                res.append(m)
        return res

    def doc_stats(self, doc_id: str) -> Dict[str, Any]:
        cnt = 0
        pages = set()
        for m in self._meta:
            if m.get("doc_id") == doc_id:
                cnt += 1
                pn = int(m.get("page_num") or 0)
                if pn > 0:
                    pages.add(pn)
        return {"chunk_count": cnt, "processed_pages": len(pages)}


_INDEX = LocalIndex()


def get_index() -> LocalIndex:
    return _INDEX
