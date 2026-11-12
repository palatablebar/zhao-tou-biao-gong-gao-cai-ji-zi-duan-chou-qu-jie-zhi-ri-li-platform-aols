"""认证控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, auth_service


def login(db: Session, email: str, password: str, request: Request) -> dict:
    result = auth_service.login(db, email, password)
    audit_service.record(
        db,
        actor_email=result["user"]["email"],
        actor_role=result["user"]["role"],
        action="auth.login",
        entity="user",
        entity_id=result["user"]["id"],
        detail={"role": result["user"]["role"]},
        layer="domain",
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def me(db: Session, email: str) -> dict:
    user = auth_service.get_user_by_email(db, email)
    if user is None:
        raise auth_service.AuthError("AUTH_MISSING", 401)
    payload = auth_service.serialize_user(user)
    payload["permissions"] = auth_service.permissions_of(user.role)
    return {"user": payload}
