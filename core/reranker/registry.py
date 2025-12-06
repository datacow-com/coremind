import os
from typing import Protocol

from core.reranker.cohere_reranker import CohereReranker as _CohereReranker
from core.reranker.cross_encoder import Reranker as _CrossEncoderReranker


class RerankerProtocol(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


def _cohere_available() -> bool:
    try:
        return bool(os.environ.get("COHERE_API_KEY"))
    except Exception:
        return False


def get_reranker(provider: str | None = None) -> RerankerProtocol:
    """
    Simple provider registry for rerankers.

    - cohere: use Cohere reranker if API key present
    - cross_encoder: use local CrossEncoder-based reranker
    - simple: fallback lexical overlap
    - auto (default): prefer cohere -> cross_encoder -> simple
    """
    name = (provider or os.environ.get("RERANKER_PROVIDER") or "auto").lower()
    if name == "cohere" and _cohere_available():
        return _CohereReranker()
    if name == "cross_encoder":
        return _CrossEncoderReranker()
    if name == "simple":
        return _CrossEncoderReranker(model_name=None)  # will use fallback overlap
    # auto
    if _cohere_available():
        return _CohereReranker()
    return _CrossEncoderReranker()
