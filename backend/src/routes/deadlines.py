from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, DEADLINE_RECOMPUTE_ROLES
from src.controllers import deadline_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import RecomputeIn

router = APIRouter(prefix="/deadlines", tags=["deadlines"])


@router.get("")
def list_events(
    as_of: str | None = None,
    risk: str | None = None,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return deadline_controller.list_events(db, as_of=as_of, risk=risk)


@router.post("/recompute")
def recompute(
    payload: RecomputeIn,
    request: Request,
    principal: Principal = Depends(require_roles(*DEADLINE_RECOMPUTE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return deadline_controller.recompute(
        db, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )
