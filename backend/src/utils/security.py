"""密码哈希与 JWT。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from src.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw, hashed)
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> tuple[str, int]:
    expires_in = settings.access_token_minutes * 60
    payload = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
