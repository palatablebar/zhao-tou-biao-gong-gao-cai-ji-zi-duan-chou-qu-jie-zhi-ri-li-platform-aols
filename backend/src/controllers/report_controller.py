"""报表控制器：总览 / 本周必投 CSV / 审计日志。"""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import Request, Response
from sqlalchemy.orm import Session

from src.services import audit_service, auth_service, report_service
from src.utils.timeutil import parse_local


def overview(db: Session) -> dict:
    return report_service.overview(db)


def weekly_csv(
    db: Session,
    *,
    role: str,
    email: str,
    request: Request,
    as_of: str | None = None,
) -> Response:
    industry = None
    if role == "client":
        user = auth_service.get_user_by_email(db, email)
        industry = user.industry if user else None
    resolved = parse_local(as_of)
    filename, content = report_service.weekly_csv(db, as_of=resolved, industry=industry)
    audit_service.record(
        db,
        actor_email=email,
        actor_role=role,
        action="report.export",
        entity="report",
        entity_id=filename,
        detail={"industry_scope": industry or "all", "bytes": len(content.encode("utf-8"))},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    # HTTP header 只能是 latin-1：ASCII 兜底名 + RFC 5987 的 UTF-8 文件名
    ascii_name = re.sub(r"[^A-Za-z0-9._-]", "", filename) or "bidsift-week.csv"
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disposition, "X-Export-Filename": quote(filename)},
    )


def audit_logs(db: Session, limit: int = 60) -> dict:
    return {"items": report_service.audit_logs(db, limit=limit)}
