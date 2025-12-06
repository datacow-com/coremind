import os
from collections.abc import Mapping
from typing import Any

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover
    trace = None


def set_span_attrs(attrs: Mapping[str, Any]) -> None:
    """Set attributes on current span if OTel is available."""
    if not trace:
        return
    deny = {
        k.strip().lower()
        for k in (os.environ.get("TRACE_SENSITIVE_KEYS") or "").split(",")
        if k.strip()
    }
    try:
        span = trace.get_current_span()
        if not span:
            return
        for k, v in attrs.items():
            if v is None:
                continue
            if k.lower() in deny:
                continue
            span.set_attribute(k, v)
    except Exception:
        return
