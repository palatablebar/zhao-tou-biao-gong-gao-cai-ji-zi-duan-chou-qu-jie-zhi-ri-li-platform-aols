from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALL_ROLES
from src.controllers import notice_controller
from src.middlewares.rbac import Principal, require_roles

router = APIRouter(prefix="/notices", tags=["notices"])


@router.get("")
def list_notices(
    q: str | None = None,
    site_id: int | None = None,
    region: str | None = None,
    category: str | None = None,
    confidence: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return notice_controller.list_notices(
        db,
        q=q,
        site_id=site_id,
        region=region,
        category=category,
        confidence=confidence,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/board-meta")
def board_meta(
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return notice_controller.board_meta(db)


@router.get("/{notice_id}")
def get_notice(
    notice_id: int,
    principal: Principal = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return notice_controller.get_notice(db, notice_id)
