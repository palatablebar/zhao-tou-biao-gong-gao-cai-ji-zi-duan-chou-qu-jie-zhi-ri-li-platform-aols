"""审计日志：领域动作由 service 记录，HTTP 层动作由中间件记录。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.audit import AuditLog
from src.utils.timeutil import iso_local


def record(
    db: Session,
    *,
    actor_email: str,
    actor_role: str,
    action: str,
    entity: str,
    entity_id: int | str | None = None,
    detail: dict | None = None,
    layer: str = "domain",
    ip: str | None = None,
    seed_key: str | None = None,
) -> AuditLog:
    if seed_key:
        existing = db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key))
        if existing is not None:
            return existing
    log = AuditLog(
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail or {},
        layer=layer,
        ip=ip,
        seed_key=seed_key,
    )
    db.add(log)
    db.flush()
    return log


def list_logs(db: Session, limit: int = 60, action: str | None = None) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()
    return [
        {
            "id": row.id,
            "actor_email": row.actor_email,
            "actor_role": row.actor_role,
            "action": row.action,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "detail": row.detail,
            "layer": row.layer,
            "created_at": iso_local(row.created_at),
        }
        for row in rows
    ]
