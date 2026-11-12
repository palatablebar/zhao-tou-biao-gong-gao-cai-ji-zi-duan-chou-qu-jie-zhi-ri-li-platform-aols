from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES, SITE_WRITE_ROLES
from src.controllers import site_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import SiteUpdateIn

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
def list_sites(
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return site_controller.list_sites(db)


@router.patch("/{site_id}")
def update_site(
    site_id: int,
    payload: SiteUpdateIn,
    request: Request,
    principal: Principal = Depends(require_roles(*SITE_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return site_controller.update_site(
        db,
        site_id,
        payload.model_dump(exclude_none=True),
        principal.email,
        principal.role,
        request,
    )
