import os
import time
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)


def _secret() -> str:
    s = os.environ.get("SECRET_KEY")
    if (os.environ.get("APP_ENV", "dev").lower() == "prod") and not s:
        raise RuntimeError("SECRET_KEY required")
    return s or "dev-secret"


def create_token(subject: str, ttl_seconds: int = 3600) -> str:
    import uuid

    payload: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "exp": int(time.time()) + ttl_seconds,
        "iat": int(time.time()),
        "name": subject,
        "role": "system_admin",
        "permissions": [
            "providers:read",
            "providers:write",
            "bindings:read",
            "bindings:write",
            "credentials:read",
            "credentials:write",
            "env:read",
            "env:apply",
            "env:rollback",
        ],
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    payload = verify_token(credentials)
    user_id = payload.get("sub", "unknown")
    user_name = payload.get("name", "Unknown User")
    user_role = payload.get("role", "user")
    return {
        "id": user_id,
        "name": user_name,
        "role": user_role,
        "email": payload.get("email", ""),
        "permissions": payload.get("permissions", []),
    }


def authorize(
    user: dict[str, Any], roles: list[str] | None = None, permissions: list[str] | None = None
) -> None:
    role_ok = True
    perm_ok = True
    if roles:
        role_ok = user.get("role") in roles
    if permissions:
        user_perms = set(user.get("permissions", []))
        perm_ok = set(permissions).issubset(user_perms)
    if not (role_ok and perm_ok):
        raise HTTPException(status_code=403, detail="Forbidden")
