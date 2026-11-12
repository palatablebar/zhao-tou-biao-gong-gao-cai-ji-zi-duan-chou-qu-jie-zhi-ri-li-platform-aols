from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, TEMPLATE_PUBLISH_ROLES, TEMPLATE_WRITE_ROLES
from src.controllers import template_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import TemplateCreateIn

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
def list_templates(
    site_id: int | None = None,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.list_templates(db, site_id=site_id)


@router.get("/compare")
def compare(
    left: int,
    right: int,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.compare_templates(db, left, right)


@router.post("")
def create_template(
    payload: TemplateCreateIn,
    request: Request,
    principal: Principal = Depends(require_roles(*TEMPLATE_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.create_template(
        db, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )


@router.post("/{template_id}/publish")
def publish_template(
    template_id: int,
    request: Request,
    principal: Principal = Depends(require_roles(*TEMPLATE_PUBLISH_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.publish_template(
        db, template_id, principal.email, principal.role, request
    )
