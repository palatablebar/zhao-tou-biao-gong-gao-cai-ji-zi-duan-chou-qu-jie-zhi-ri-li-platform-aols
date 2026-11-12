"""角色鉴权依赖：401 未登录 / 403 角色不足（后端真实拦截，不依赖前端隐藏按钮）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Request

from src.constants.roles import PERMISSIONS
from src.utils.errors import AppError


@dataclass
class Principal:
    email: str
    role: str


def _principal(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise AppError("AUTH_MISSING", 401)
    return Principal(email=principal["email"], role=principal["role"])


def current_principal(request: Request) -> Principal:
    return _principal(request)


def require_roles(*roles: str) -> Callable[[Request], Principal]:
    def dependency(request: Request) -> Principal:
        principal = _principal(request)
        if principal.role not in roles:
            raise AppError(
                "FORBIDDEN",
                403,
                detail=f"role={principal.role} required={','.join(roles)}",
            )
        return principal

    return dependency


def require_permission(permission: str) -> Callable[[Request], Principal]:
    def dependency(request: Request) -> Principal:
        principal = _principal(request)
        if permission not in PERMISSIONS.get(principal.role, set()):
            raise AppError("FORBIDDEN", 403, detail=f"permission={permission}")
        return principal

    return dependency
