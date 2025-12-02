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
        t = re.sub(r"[\p{P}\p{S}]", " ", t)
        # fallback: basic punctuation strip if \p classes unsupported
        t = re.sub(r"[\.,;:!\?\-_/\\()\[\]{}<>\|\^\$\*\+\=\"]", " ", t)
        # split by whitespace; keep CJK chars as individual tokens
        tokens: list[str] = []
        for ch in t:
            if "\u4e00" <= ch <= "\u9fff":
                tokens.append(ch)
            else:
                # accumulate non-CJK sequences
                pass
        # combine CJK + ascii tokens
        words = []
        buf = []
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


def get_keyword_index() -> KeywordIndex:
    return _KEYWORDS
