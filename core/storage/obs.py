from typing import Any

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover
    trace = None

try:
    import prometheus_client
except Exception:  # pragma: no cover
    prometheus_client = None


if prometheus_client:
    VECTOR_SEARCH_DURATION_MS = prometheus_client.Histogram(
        "vector_search_duration_ms",
        "Vector search duration (ms)",
        buckets=(5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000),
    )
    VECTOR_SEARCH_COUNT = prometheus_client.Counter(
        "vector_search_count",
        "Vector search request count",
        ["backend", "collection"],
    )
    VECTOR_SEARCH_ERRORS = prometheus_client.Counter(
        "vector_search_errors",
        "Vector search errors",
        ["backend", "collection"],
    )
else:  # pragma: no cover
    VECTOR_SEARCH_DURATION_MS = None
    VECTOR_SEARCH_COUNT = None
    VECTOR_SEARCH_ERRORS = None


def record_vector_search(
    backend: str,
    collection: str | None,
    duration_ms: float,
    attrs: dict[str, Any] | None = None,
) -> None:
    if VECTOR_SEARCH_DURATION_MS:
        try:
            VECTOR_SEARCH_DURATION_MS.observe(duration_ms)
        except Exception:
            pass
    if VECTOR_SEARCH_COUNT:
        try:
            VECTOR_SEARCH_COUNT.labels(backend=backend, collection=collection or "").inc()
        except Exception:
            pass
    if VECTOR_SEARCH_ERRORS and attrs and "error" in attrs:
        try:
            VECTOR_SEARCH_ERRORS.labels(backend=backend, collection=collection or "").inc()
        except Exception:
            pass
    if trace:
        try:
            span = trace.get_current_span()
            if span:
                span.set_attribute("vector.backend", backend)
                if collection:
                    span.set_attribute("vector.collection", collection)
                span.set_attribute("vector.duration_ms", duration_ms)
                for k, v in (attrs or {}).items():
                    if v is not None:
                        span.set_attribute(f"vector.{k}", v)
        except Exception:
            pass
