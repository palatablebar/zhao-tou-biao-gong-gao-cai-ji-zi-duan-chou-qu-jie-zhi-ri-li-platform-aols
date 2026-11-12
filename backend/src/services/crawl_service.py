"""采集批次：模拟抓取 6 个采源 → 去重入库 → 全量重算抽取 → 同步日历风险。"""
from __future__ import annotations

import time
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import FieldStatus
from src.models.crawl_run import CrawlRun
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.services import deadline_service, extraction_engine, field_service, source_catalog, template_service
from src.utils.errors import AppError
from src.utils.timeutil import iso_local, now_local


def serialize_run(db: Session, run: CrawlRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "triggered_by": run.triggered_by,
        "site_count": run.site_count,
        "fetched_count": run.fetched_count,
        "inserted_count": run.inserted_count,
        "duplicate_count": run.duplicate_count,
        "error_count": run.error_count,
        "field_count": run.field_count,
        "low_confidence_count": run.low_confidence_count,
        "duration_ms": run.duration_ms,
        "note": run.note,
        "started_at": iso_local(run.started_at),
        "finished_at": iso_local(run.finished_at),
    }


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    runs = db.scalars(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(limit)).all()
    return [serialize_run(db, run) for run in runs]


def _ensure_notice(db: Session, site: Site, payload: dict, run_id: int) -> str:
    notice = db.scalar(
        select(Notice).where(Notice.site_id == site.id, Notice.external_id == payload["external_id"])
    )
    if notice is None:
        notice = Notice(
            site_id=site.id,
            crawl_run_id=run_id,
            external_id=payload["external_id"],
            title=payload["title"],
            url=payload["url"],
            publisher=payload["publisher"],
            region=payload["region"],
            category=payload["category"],
            industry=payload["industry"],
            published_at=payload["published_at"],
            qualification=payload["qualification"],
            body_kind=payload["body_kind"],
            raw_html=payload["raw_html"],
            clean_text=payload["clean_text"],
            content_hash=payload["content_hash"],
            byte_size=payload["byte_size"],
            status=payload["status"],
        )
        db.add(notice)
        db.flush()
        return "inserted"
    if notice.content_hash != payload["content_hash"]:
        notice.raw_html = payload["raw_html"]
        notice.clean_text = payload["clean_text"]
        notice.content_hash = payload["content_hash"]
        notice.byte_size = payload["byte_size"]
        db.flush()
        return "updated"
    return "duplicate"


def extract_all(db: Session, site_ids: list[int] | None = None) -> dict:
    stmt = select(Notice)
    if site_ids:
        stmt = stmt.where(Notice.site_id.in_(site_ids))
    notices = db.scalars(stmt.order_by(Notice.id)).all()
    created = updated = preserved = total = low = 0
    for notice in notices:
        anchors = template_service.anchors_for_site(db, notice.site_id)
        results = extraction_engine.extract_notice(notice.clean_text, notice.published_at, anchors)
        existing = {
            field.field_key: field
            for field in db.scalars(
                select(ExtractedField).where(ExtractedField.notice_id == notice.id)
            ).all()
        }
        for field_key, result in results.items():
            total += 1
            field = existing.get(field_key)
            if field is None:
                field = ExtractedField(notice_id=notice.id, field_key=field_key)
                db.add(field)
                field_service.apply_result(field, result)
                created += 1
            elif field.status in field_service.PRESERVED_STATUSES:
                preserved += 1
            else:
                field_service.apply_result(field, result)
                updated += 1
            if (
                field.confidence < settings.low_confidence_threshold
                and field.status == FieldStatus.EXTRACTED.value
            ):
                low += 1
    db.flush()
    return {
        "field_count": total,
        "created": created,
        "updated": updated,
        "preserved_manual": preserved,
        "low_confidence_count": low,
        "notice_count": len(notices),
    }


def run_crawl(
    db: Session,
    actor_email: str,
    site_ids: list[int] | None = None,
    as_of: datetime | None = None,
) -> dict:
    running = db.scalar(select(CrawlRun).where(CrawlRun.status == "running"))
    if running is not None:
        raise AppError("CRAWL_BUSY", 409, detail=f"run_id={running.id}")
    started = time.perf_counter()
    run = CrawlRun(status="running", triggered_by=actor_email)
    db.add(run)
    db.flush()
    fetched = inserted = duplicated = updated = errors = 0
    try:
        stmt = select(Site).order_by(Site.priority)
        if site_ids:
            stmt = stmt.where(Site.id.in_(site_ids))
        sites = db.scalars(stmt).all()
        for site in sites:
            payloads = source_catalog.notices_for_site(site.domain)
            for payload in payloads:
                fetched += 1
                try:
                    outcome = _ensure_notice(db, site, payload, run.id)
                except Exception:  # noqa: BLE001 - 单条失败不影响整批
                    errors += 1
                    continue
                if outcome == "inserted":
                    inserted += 1
                elif outcome == "updated":
                    updated += 1
                else:
                    duplicated += 1
        deadline_service.ensure_tracked_events(db)
        extraction = extract_all(db, [site.id for site in sites])
        risk = deadline_service.recompute_events(db, as_of=as_of)
        run.site_count = len(sites)
        run.fetched_count = fetched
        run.inserted_count = inserted
        run.duplicate_count = duplicated
        run.error_count = errors
        run.field_count = extraction["field_count"]
        run.low_confidence_count = extraction["low_confidence_count"]
        run.status = "success"
        run.note = (
            f"去重命中 {duplicated} 条（content_hash 一致）；更新正文 {updated} 条；"
            f"抽取字段 {extraction['field_count']}，低置信 {extraction['low_confidence_count']}"
        )
        run.finished_at = now_local()
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        db.flush()
        return {
            "run": serialize_run(db, run),
            "extraction": extraction,
            "risk": risk,
        }
    except Exception as exc:
        run.status = "failed"
        run.note = f"采集失败：{exc}"[:255]
        run.finished_at = now_local()
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        db.flush()
        raise


def summary(db: Session) -> dict:
    notices = db.scalar(select(func.count()).select_from(Notice)) or 0
    fields = db.scalar(select(func.count()).select_from(ExtractedField)) or 0
    runs = db.scalar(select(func.count()).select_from(CrawlRun)) or 0
    latest = db.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()))
    return {
        "notice_count": notices,
        "field_count": fields,
        "run_count": runs,
        "latest_run": serialize_run(db, latest) if latest else None,
    }
