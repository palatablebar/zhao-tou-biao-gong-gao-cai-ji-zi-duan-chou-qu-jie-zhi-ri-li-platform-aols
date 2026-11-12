from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CRAWL_EXECUTE_ROLES
from src.controllers import crawl_controller
from src.middlewares.rbac import Principal, require_roles
from src.schemas import CrawlStartIn

router = APIRouter(prefix="/crawls", tags=["crawls"])


@router.get("")
def list_runs(
    limit: int = 20,
    principal: Principal = Depends(require_roles(*CRAWL_EXECUTE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return crawl_controller.list_runs(db, limit=limit)


@router.post("")
def start_crawl(
    payload: CrawlStartIn,
    request: Request,
    principal: Principal = Depends(require_roles(*CRAWL_EXECUTE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return crawl_controller.start_crawl(
        db, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )


@router.post("/extract")
def extract_now(
    request: Request,
    principal: Principal = Depends(require_roles(*CRAWL_EXECUTE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return crawl_controller.extract_now(db, principal.email, principal.role, request)
