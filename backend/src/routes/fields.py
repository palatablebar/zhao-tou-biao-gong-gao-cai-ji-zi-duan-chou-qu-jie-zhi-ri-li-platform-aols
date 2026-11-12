from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, FIELD_REVIEW_ROLES, REVIEW_READ_ROLES
from src.controllers import field_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import FieldCorrectIn, FieldNoteIn

router = APIRouter(tags=["fields"])


@router.get("/fields/{field_id}")
def get_field(
    field_id: int,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.get_field(db, field_id)


@router.patch("/fields/{field_id}")
def correct_field(
    field_id: int,
    payload: FieldCorrectIn,
    request: Request,
    principal: Principal = Depends(require_roles(*FIELD_REVIEW_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.correct(
        db, field_id, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )


@router.post("/fields/{field_id}/verify")
def verify_field(
    field_id: int,
    request: Request,
    principal: Principal = Depends(require_roles(*FIELD_REVIEW_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.verify(db, field_id, principal.email, principal.role, request)


@router.post("/fields/{field_id}/reject")
def reject_field(
    field_id: int,
    payload: FieldNoteIn,
    request: Request,
    principal: Principal = Depends(require_roles(*FIELD_REVIEW_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.reject(
        db, field_id, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )


@router.get("/review/queue")
def review_queue(
    threshold: float | None = None,
    principal: Principal = Depends(require_roles(*REVIEW_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.review_queue(db, threshold=threshold)


@router.get("/review/gaps")
def review_gaps(
    principal: Principal = Depends(require_roles(*REVIEW_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return field_controller.gaps(db)
