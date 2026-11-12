"""抽取字段控制器：复核队列 / 漏抽报表 / 人工修正。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, field_service


def review_queue(db: Session, threshold: float | None = None) -> dict:
    return field_service.review_queue(db, threshold=threshold)


def gaps(db: Session) -> dict:
    return field_service.gaps_report(db)


def get_field(db: Session, field_id: int) -> dict:
    return {"field": field_service.serialize_field(db, field_service.get_field(db, field_id))}


def _audit(db: Session, *, action: str, field_id: int, detail: dict, actor_email: str, actor_role: str, request: Request) -> None:
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        entity="extracted_field",
        entity_id=field_id,
        detail=detail,
        ip=request.client.host if request.client else None,
    )
    db.commit()


def correct(db: Session, field_id: int, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    result = field_service.correct_field(db, field_id, payload, actor_email)
    _audit(
        db,
        action="field.correct",
        field_id=field_id,
        detail={"previous": result["previous_value"], "value": result["field"]["value_text"]},
        actor_email=actor_email,
        actor_role=actor_role,
        request=request,
    )
    return result


def verify(db: Session, field_id: int, actor_email: str, actor_role: str, request: Request) -> dict:
    result = field_service.verify_field(db, field_id, actor_email)
    _audit(
        db,
        action="field.verify",
        field_id=field_id,
        detail={"value": result["field"]["value_text"], "confidence": result["field"]["confidence"]},
        actor_email=actor_email,
        actor_role=actor_role,
        request=request,
    )
    return result


def reject(db: Session, field_id: int, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    result = field_service.reject_field(db, field_id, actor_email, (payload or {}).get("note"))
    _audit(
        db,
        action="field.reject",
        field_id=field_id,
        detail={"note": (payload or {}).get("note")},
        actor_email=actor_email,
        actor_role=actor_role,
        request=request,
    )
    return result
