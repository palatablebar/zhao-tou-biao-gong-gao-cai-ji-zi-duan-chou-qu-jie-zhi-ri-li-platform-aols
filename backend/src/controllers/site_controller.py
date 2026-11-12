"""采源站点控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, site_service


def list_sites(db: Session) -> dict:
    return {"items": site_service.list_sites(db)}


def update_site(db: Session, site_id: int, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    result = site_service.update_site(db, site_id, payload)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="site.update",
        entity="site",
        entity_id=site_id,
        detail=result["changed"],
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result
