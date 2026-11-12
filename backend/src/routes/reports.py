from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, AUDIT_READ_ROLES
from src.controllers import report_controller
from src.middlewares.rbac import Principal, require_roles

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview")
def overview(
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.overview(db)


@router.get("/weekly-must-bid.csv")
def weekly_csv(
    request: Request,
    as_of: str | None = None,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
):
    return report_controller.weekly_csv(
        db, role=principal.role, email=principal.email, request=request, as_of=as_of
    )


@router.get("/audit")
def audit_logs(
    limit: int = 60,
    principal: Principal = Depends(require_roles(*AUDIT_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.audit_logs(db, limit=limit)
