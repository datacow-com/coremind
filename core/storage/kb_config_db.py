import os
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, text


def _db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://omnirag:omnirag_password@postgres:5432/omnirag",
    )


@lru_cache(maxsize=1)
def _engine():
    return create_engine(_db_url(), future=True)


def load_kb(name: str) -> dict[str, Any] | None:
    try:
        eng = _engine()
        with eng.connect() as conn:
            row = conn.execute(
                text("select config from kb_configs where name = :n"), {"n": name}
            ).scalar_one_or_none()
            if row is None:
                return None
            return dict(row) if isinstance(row, dict) else row
    except Exception:
        return None


def save_kb(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    eng = _engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                "insert into kb_configs(name, config) values(:n, :c) "
                "on conflict (name) do update set config = excluded.config, updated_at = now()"
            ),
            {"n": name, "c": cfg},
        )
    return cfg


def list_kbs() -> list[str]:
    try:
        eng = _engine()
        with eng.connect() as conn:
            rows = conn.execute(text("select name from kb_configs")).scalars().all()
            return [str(r) for r in rows]
    except Exception:
        return []


def register_doc(kb_name: str, entry: dict[str, Any]) -> None:
    eng = _engine()
    with eng.begin() as conn:
        conn.execute(
            text(
                "insert into kb_documents(id, kb_name, filename, path, uploaded_at, metadata) "
                "values(:id, :kb, :fn, :path, :ts, :meta) "
                "on conflict (id) do update set kb_name = excluded.kb_name, "
                "filename = excluded.filename, path = excluded.path, uploaded_at = excluded.uploaded_at, metadata = excluded.metadata, updated_at = now()"
            ),
            {
                "id": entry.get("id"),
                "kb": kb_name,
                "fn": entry.get("filename"),
                "path": entry.get("path"),
                "ts": int(entry.get("uploaded_at") or 0),
                "meta": entry.get("metadata") or {},
            },
        )


def remove_doc(doc_id: str, kb_name: str | None = None) -> None:
    eng = _engine()
    with eng.begin() as conn:
        if kb_name:
            conn.execute(
                text("delete from kb_documents where id = :id and kb_name = :kb"),
                {"id": doc_id, "kb": kb_name},
            )
        else:
            conn.execute(text("delete from kb_documents where id = :id"), {"id": doc_id})
