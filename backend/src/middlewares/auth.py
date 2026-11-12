"""JWT 中间件：解析 Authorization 头，把 principal 挂到 request.state（不在此拦截）。"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.utils.security import decode_access_token


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.principal = None
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            payload = decode_access_token(header.split(" ", 1)[1].strip())
            if payload and payload.get("sub"):
                request.state.principal = {
                    "email": payload["sub"],
                    "role": payload.get("role", ""),
                }
        return await call_next(request)
