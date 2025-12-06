import asyncio
import json
import os
import time
from typing import Any
from uuid import uuid4

from server.config import settings

_LOCK = asyncio.Lock()


def _sessions_path() -> str:
    base = settings.uploads_dir_resolved
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "chat_sessions.json")


async def _load() -> list[dict[str, Any]]:
    path = _sessions_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


async def _save(sessions: list[dict[str, Any]]) -> None:
    path = _sessions_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


async def list_sessions() -> list[dict[str, Any]]:
    async with _LOCK:
        sessions = await _load()
        return sorted(sessions, key=lambda x: x.get("updated_at", 0), reverse=True)


async def create_session(payload: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    item = {
        "id": payload.get("id") or str(uuid4()),
        "name": payload.get("name") or "会话",
        "kb_name": payload.get("kb_name"),
        "config": payload.get("config") or {},
        "created_at": now,
        "updated_at": now,
    }
    async with _LOCK:
        sessions = await _load()
        sessions.append(item)
        await _save(sessions)
    return item


async def update_session(sid: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    async with _LOCK:
        sessions = await _load()
        found = None
        for s in sessions:
            if s.get("id") == sid:
                s.update(
                    {
                        "name": payload.get("name", s.get("name")),
                        "kb_name": payload.get("kb_name", s.get("kb_name")),
                        "config": payload.get("config", s.get("config") or {}),
                        "updated_at": int(time.time()),
                    }
                )
                found = s
                break
        if found:
            await _save(sessions)
        return found


async def delete_session(sid: str) -> bool:
    async with _LOCK:
        sessions = await _load()
        new_list = [s for s in sessions if s.get("id") != sid]
        if len(new_list) == len(sessions):
            return False
        await _save(new_list)
        return True
