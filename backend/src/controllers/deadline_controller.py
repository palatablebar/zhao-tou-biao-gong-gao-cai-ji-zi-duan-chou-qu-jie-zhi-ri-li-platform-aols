"""截止日历控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, deadline_service


def list_events(db: Session, as_of: str | None = None, risk: str | None = None) -> dict:
    resolved = deadline_service.resolve_as_of(as_of)
    events = deadline_service.list_events(db, as_of=resolved, risk=risk)
    must_bid = deadline_service.week_must_bid_rows(db, as_of=resolved)
    return {
        "items": events,
        "as_of": resolved.isoformat(timespec="seconds"),
        "formula": deadline_service.FORMULA,
        "week_must_bid_count": len(must_bid),
    }


def recompute(db: Session, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    as_of = deadline_service.resolve_as_of((payload or {}).get("as_of"))
    result = deadline_service.recompute_events(db, as_of=as_of)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="deadline.recompute",
        entity="deadline_event",
        entity_id=None,
        detail={"as_of": result["as_of"], "counts": result["counts"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result
