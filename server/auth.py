import os
import time
from typing import Any, Dict
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt


security = HTTPBearer()


def _secret() -> str:
    return os.environ.get("SECRET_KEY", "dev-secret")


def create_token(subject: str, ttl_seconds: int = 3600) -> str:
    payload: Dict[str, Any] = {
        "sub": subject,
        "exp": int(time.time()) + ttl_seconds,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

