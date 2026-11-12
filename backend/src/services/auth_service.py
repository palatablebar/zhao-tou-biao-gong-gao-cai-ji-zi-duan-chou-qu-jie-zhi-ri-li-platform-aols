"""认证：登录 / 当前用户。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.error_codes import ERROR_CODES
from src.constants.roles import ROLE_LABELS, has_permission
from src.models.user import User
from src.utils.security import create_access_token, verify_password


class AuthError(Exception):
    def __init__(self, code: str, status_code: int = 401) -> None:
        self.code = code
        self.status_code = status_code
        self.message = ERROR_CODES.get(code, code)
        super().__init__(self.message)


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "role_label": ROLE_LABELS.get(user.role, user.role),
        "industry": user.industry,
    }


def login(db: Session, email: str, password: str) -> dict:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("AUTH_INVALID", 401)
    token, expires_in = create_access_token(user.email, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": serialize_user(user),
    }


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def permissions_of(role: str) -> list[str]:
    from src.constants.roles import PERMISSIONS

    return sorted(PERMISSIONS.get(role, set()))


def can(role: str, permission: str) -> bool:
    return has_permission(role, permission)
