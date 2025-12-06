from typing import Any

from server.config import settings


class KeywordIndex:
    def __init__(self):
        self._corpus: list[str] = []
        self._meta: list[dict[str, Any]] = []
        self._bm25 = None
        self._token_cache: list[list[str]] = []

    def _tokenize(self, text: str) -> list[str]:
        import re

        t = (text or "").lower()
        try:
            t = re.sub(r"[\p{P}\p{S}]", " ", t)
        except Exception:
            pass
        # fallback: basic punctuation strip if \p classes unsupported
        t = re.sub(r"[\.,;:!\?\-_/\\\(\)\[\]{}<>\|\^\$\*\+\=\"]", " ", t)
        # split by whitespace; keep CJK chars as individual tokens
        tokens: list[str] = []
        for ch in t:
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
            else:
                # accumulate non-CJK sequences
                pass
        # combine CJK + ascii tokens
        words: list[str] = []
        buf: list[str] = []
        for ch in t:
            if "\u4e00" <= ch <= "\u9fff":
                if buf:
                    words.extend(" ".join(buf).split())
                    buf = []
                words.append(ch)
            else:
                buf.append(ch)
        if buf:
            words.extend(" ".join(buf).split())
        tokens = [w for w in words if w]
        if getattr(settings, "stop_words_enabled", False):
            sw = set(getattr(settings, "stop_words", []) or [])
            tokens = [w for w in tokens if w not in sw]
        return tokens

    def _ensure(self):
        if self._bm25 is None and self._corpus:
            from rank_bm25 import BM25Okapi

            tokenized_corpus = [self._tokenize(c) for c in self._corpus]
            self._bm25 = BM25Okapi(tokenized_corpus)

    def add(self, content: str, meta: dict[str, Any]) -> None:
        self._corpus.append(content or "")
        self._meta.append(meta)
        # Invalidate bm25, rebuild lazy on next search
        self._bm25 = None

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self._corpus:
            return []
        self._ensure()
        q_tokens = self._tokenize(query)
        scores = list(self._bm25.get_scores(q_tokens))
        tw = getattr(settings, "term_weights", {}) or {}
        if tw:
            boost = 1.0
            for qt in q_tokens:
                w = float(tw.get(qt) or 0.0)
                if w:
                    boost += w
            scores = [float(s) * float(boost) for s in scores]
        idx = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
        return [(self._meta[i], float(scores[i])) for i in idx]


_KEYWORDS = KeywordIndex()


class KeywordElasticsearch:
    def __init__(self):
        self.client = None
        self.index = None
        self.available = False
        self._init()

    def _init(self):
        try:
            from elasticsearch import Elasticsearch

            from server.config import settings as _settings

            url = getattr(_settings, "elasticsearch_url", None) or "http://localhost:9200"
            idx = getattr(_settings, "elasticsearch_index", None) or "omnirag_chunks"
            self.client = Elasticsearch(url, verify_certs=False)
            self.index = idx
            self.available = True
        except Exception:
            self.available = False

    def add(self, content: str, meta: dict[str, Any]) -> None:
        if not self.available or self.client is None:
            return
        try:
            self.client.index(
                index=self.index,
                id=f"{meta.get('id')}-kw",
                document={
                    "chunk_id": meta.get("id"),
                    "document_id": meta.get("doc_id"),
                    "content": content,
                    "page_number": int(meta.get("page_num") or 0),
                    "chunk_index": int(meta.get("chunk_index") or 0),
                    "metadata": meta.get("metadata", {}),
                },
                refresh=True,
            )
        except Exception:
            pass

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict[str, Any], float]]:
        if not self.available or self.client is None:
            return []
        try:
            body = {
                "size": top_k,
                "query": {"match": {"content": query}},
                "_source": [
                    "chunk_id",
                    "document_id",
                    "content",
                    "page_number",
                    "chunk_index",
                    "metadata",
                ],
            }
            res = self.client.search(index=self.index, body=body)
            hits = res.get("hits", {}).get("hits", [])
            out: list[tuple[dict[str, Any], float]] = []
            for h in hits:
                s = float(h.get("_score") or 0.0)
                src = h.get("_source") or {}
                out.append(
                    (
                        {
                            "id": src.get("chunk_id"),
                            "content": src.get("content"),
                            "page_num": src.get("page_number"),
                            "doc_id": src.get("document_id"),
                            "chunk_index": src.get("chunk_index"),
                            "metadata": src.get("metadata", {}),
                        },
                        s,
                    )
                )
            return out
        except Exception:
            return []


def get_keyword_index() -> Any:
    kb = (getattr(settings, "keyword_backend", None) or "local").lower()
    if kb == "elasticsearch":
        es = KeywordElasticsearch()
        if es.available:
            return es
    return _KEYWORDS
