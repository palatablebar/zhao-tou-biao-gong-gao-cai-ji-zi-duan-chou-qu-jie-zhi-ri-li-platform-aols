"""审计中间件：写请求落一条 HTTP 层审计（领域层动作由 service/controller 再记一条）。"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.config.database import SessionLocal
from src.services import audit_service
from src.utils.security import decode_access_token

MUTATING = {"POST", "PATCH", "PUT", "DELETE"}
SKIP_PATHS = {"/api/health", "/health"}


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            path = request.url.path
            if request.method in MUTATING and path not in SKIP_PATHS and response.status_code < 500:
                email, role = "anonymous", "anonymous"
                header = request.headers.get("authorization", "")
                if header.lower().startswith("bearer "):
                    payload = decode_access_token(header.split(" ", 1)[1].strip()) or {}
                    email = payload.get("sub", "anonymous")
                    role = payload.get("role", "anonymous")
                segments = [item for item in path.split("/") if item]
                entity = segments[1] if len(segments) > 1 else "api"
                with SessionLocal() as db:
                    audit_service.record(
                        db,
                        actor_email=email,
                        actor_role=role,
                        action="http.mutation",
                        entity=entity,
                        entity_id=None,
                        detail={"path": path, "method": request.method, "status": response.status_code},
                        layer="http",
                        ip=request.client.host if request.client else None,
                    )
                    db.commit()
        except Exception:  # noqa: BLE001 - 审计失败不影响主流程
            pass
        return response
