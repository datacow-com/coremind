import os
import time
from collections.abc import Callable
from typing import Any

from fastapi import UploadFile

from core.nodes.retrieve import _scan_file, _validate_upload  # reuse existing checks


def save_and_register(
    file: UploadFile,
    kb_name: str | None,
    dest_path: str,
    kb_register: Callable[[str, dict[str, Any]], None],
    content: bytes | None = None,
) -> dict[str, Any]:
    if content is None:
        if hasattr(file, "file"):
            file.file.seek(0)
            content = file.file.read()
        else:
            content = b""
    _validate_upload(file, content)
    with open(dest_path, "wb") as f:
        f.write(content)
    _scan_file(dest_path)
    if kb_name:
        kb_register(
            str(kb_name),
            {
                "id": os.path.basename(dest_path),
                "filename": str(file.filename or os.path.basename(dest_path)),
                "path": dest_path,
                "uploaded_at": int(time.time()),
            },
        )
    return {"path": dest_path, "kb_name": kb_name}


def ensure_upload_dir(base: str) -> str:
    os.makedirs(base, exist_ok=True)
    return base
