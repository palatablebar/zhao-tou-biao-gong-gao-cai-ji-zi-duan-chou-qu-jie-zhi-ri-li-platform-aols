"""采集批次控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, crawl_service, deadline_service
from src.utils.timeutil import parse_local


def start_crawl(db: Session, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    as_of = deadline_service.resolve_as_of(payload.get("as_of")) if payload.get("as_of") else None
    result = crawl_service.run_crawl(
        db,
        actor_email=actor_email,
        site_ids=payload.get("site_ids"),
        as_of=as_of,
    )
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="crawl.run",
        entity="crawl_run",
        entity_id=result["run"]["id"],
        detail={
            "fetched": result["run"]["fetched_count"],
            "inserted": result["run"]["inserted_count"],
            "duplicate": result["run"]["duplicate_count"],
            "fields": result["run"]["field_count"],
            "low_confidence": result["run"]["low_confidence_count"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def list_runs(db: Session, limit: int = 20) -> dict:
    return {
        "items": crawl_service.list_runs(db, limit=limit),
        "summary": crawl_service.summary(db),
    }


def extract_now(db: Session, actor_email: str, actor_role: str, request: Request) -> dict:
    """对全库公告重跑一次抽取（保留人工已复核字段）。"""
    result = crawl_service.extract_all(db)
    deadline_service.recompute_events(db)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="extract.rerun",
        entity="extracted_field",
        entity_id=None,
        detail=result,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def parse_as_of(value: str | None):
    return parse_local(value)
