from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, TEMPLATE_PUBLISH_ROLES, TEMPLATE_WRITE_ROLES
from src.controllers import template_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import PublishIn, TemplateCreateIn

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


@router.get("/{template_id}/publish-preview")
def preview_publish(
    template_id: int,
    as_of: str | None = None,
    principal: Principal = Depends(require_roles(*TEMPLATE_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    """按目标版本的规则试算该采源历史公告的影响面（只读，不落库）。"""
    return template_controller.preview_publish(db, template_id, as_of=as_of)


@router.post("/{template_id}/publish")
def publish_template(
    template_id: int,
    request: Request,
    payload: PublishIn | None = None,
    principal: Principal = Depends(require_roles(*TEMPLATE_PUBLISH_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return template_controller.publish_template(
        db,
        template_id,
        principal.email,
        principal.role,
        request,
        as_of=(payload.as_of if payload else None),
    )
