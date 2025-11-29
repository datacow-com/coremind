from typing import Dict, Any, List, Tuple


class KeywordIndex:
    def __init__(self):
        self._corpus: List[str] = []
        self._meta: List[Dict[str, Any]] = []
        self._bm25 = None

    def _ensure(self):
        if self._bm25 is None and self._corpus:
            from rank_bm25 import BM25Okapi
            tokenized_corpus = [c.lower().split() for c in self._corpus]
            self._bm25 = BM25Okapi(tokenized_corpus)

    def add(self, content: str, meta: Dict[str, Any]) -> None:
        self._corpus.append(content or "")
        self._meta.append(meta)
        # Invalidate bm25, rebuild lazy on next search
        self._bm25 = None

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if not self._corpus:
            return []
        self._ensure()
        scores = list(self._bm25.get_scores(query.lower().split()))
        idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
        return [(self._meta[i], float(scores[i])) for i in idx]


_KEYWORDS = KeywordIndex()


def get_keyword_index() -> KeywordIndex:
    return _KEYWORDS

