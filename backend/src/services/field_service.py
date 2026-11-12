"""抽取字段：复核队列 / 人工修正 / 漏抽报表 / 抽取结果落库。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import FIELD_ORDER, FieldStatus, NoticeStatus
from src.constants.fieldspec import FIELD_SPEC
from src.constants.limits import MAX_FIELD_VALUE_LENGTH, REVIEW_QUEUE_LIMIT
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.services import deadline_service, extraction_engine
from src.utils.errors import AppError
from src.utils.textutil import comma_number
from src.utils.timeutil import iso_local, now_local

PRESERVED_STATUSES = (FieldStatus.VERIFIED.value, FieldStatus.CORRECTED.value)


def apply_result(field: ExtractedField, result: dict) -> None:
    field.value_text = (result.get("value_text") or None)
    field.raw_text = result.get("raw_text")
    field.unit = result.get("unit")
    field.amount_yuan = result.get("amount_yuan")
    field.event_at = result.get("event_at")
    field.precision = result.get("precision") or "missing"
    field.is_estimated = bool(result.get("is_estimated"))
    field.anchor_score = float(result.get("anchor_score") or 0.0)
    field.format_score = float(result.get("format_score") or 0.0)
    field.clarity_score = float(result.get("clarity_score") or 0.0)
    field.confidence = float(result.get("confidence") or 0.0)
    field.reason = (result.get("reason") or "")[:400]
    field.extracted_at = now_local()


def serialize_field(db: Session, field: ExtractedField, notice: Notice | None = None) -> dict:
    notice = notice or db.get(Notice, field.notice_id)
    return {
        "id": field.id,
        "notice_id": field.notice_id,
        "field_key": field.field_key,
        "label": FIELD_SPEC.get(field.field_key, {}).get("label", field.field_key),
        "value_text": field.value_text,
        "raw_text": field.raw_text,
        "unit": field.unit,
        "amount_yuan": field.amount_yuan,
        "amount_wan": round((field.amount_yuan or 0) / 10000, 2) if field.amount_yuan else None,
        "event_at": iso_local(field.event_at),
        "precision": field.precision,
        "is_estimated": field.is_estimated,
        "anchor_score": field.anchor_score,
        "format_score": field.format_score,
        "clarity_score": field.clarity_score,
        "confidence": field.confidence,
        "low_confidence": field.confidence < settings.low_confidence_threshold,
        "reason": field.reason,
        "status": field.status,
        "reviewer": field.reviewer,
        "reviewed_at": iso_local(field.reviewed_at),
        "extracted_at": iso_local(field.extracted_at),
        "notice": None
        if notice is None
        else {
            "id": notice.id,
            "external_id": notice.external_id,
            "title": notice.title,
            "region": notice.region,
            "category": notice.category,
            "industry": notice.industry,
            "site_id": notice.site_id,
            "status": notice.status,
            "published_at": iso_local(notice.published_at),
        },
    }


def get_field(db: Session, field_id: int) -> ExtractedField:
    field = db.get(ExtractedField, field_id)
    if field is None:
        raise AppError("NOT_FOUND", 404, detail=f"field_id={field_id}")
    return field


def review_queue(db: Session, threshold: float | None = None, limit: int = REVIEW_QUEUE_LIMIT) -> dict:
    limit_value = threshold if threshold is not None else settings.low_confidence_threshold
    rows = db.execute(
        select(ExtractedField, Notice)
        .join(Notice, Notice.id == ExtractedField.notice_id)
        .where(
            ExtractedField.confidence < limit_value,
            ExtractedField.status == FieldStatus.EXTRACTED.value,
        )
        .order_by(ExtractedField.confidence.asc(), ExtractedField.id.asc())
        .limit(limit)
    ).all()
    items = [serialize_field(db, field, notice) for field, notice in rows]
    pending_total = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .where(
            ExtractedField.confidence < limit_value,
            ExtractedField.status == FieldStatus.EXTRACTED.value,
        )
    ) or 0
    by_field: dict[str, int] = {key: 0 for key in FIELD_ORDER}
    for item in items:
        by_field[item["field_key"]] = by_field.get(item["field_key"], 0) + 1
    reviewed_total = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .where(ExtractedField.status.in_([FieldStatus.VERIFIED.value, FieldStatus.CORRECTED.value]))
    ) or 0
    return {
        "threshold": limit_value,
        "pending_total": pending_total,
        "returned": len(items),
        "reviewed_total": reviewed_total,
        "by_field": by_field,
        "items": items,
    }


def gaps_report(db: Session) -> dict:
    rows = db.execute(
        select(ExtractedField, Notice.site_id, Site.name)
        .join(Notice, Notice.id == ExtractedField.notice_id)
        .join(Site, Site.id == Notice.site_id)
    ).all()
    sites = {site.id: site for site in db.scalars(select(Site).order_by(Site.priority)).all()}
    matrix: dict[tuple[int, str], dict] = {}
    for field, site_id, _site_name in rows:
        key = (site_id, field.field_key)
        bucket = matrix.setdefault(
            key,
            {
                "total": 0,
                "missing": 0,
                "low": 0,
                "confidence_sum": 0.0,
            },
        )
        bucket["total"] += 1
        if field.value_text is None:
            bucket["missing"] += 1
        if field.confidence < settings.low_confidence_threshold:
            bucket["low"] += 1
        bucket["confidence_sum"] += field.confidence
    site_rows: list[dict] = []
    field_totals: dict[str, dict] = {
        key: {"total": 0, "missing": 0, "low": 0, "confidence_sum": 0.0} for key in FIELD_ORDER
    }
    for site_id, site in sites.items():
        field_cells = []
        for field_key in FIELD_ORDER:
            bucket = matrix.get((site_id, field_key), {"total": 0, "missing": 0, "low": 0, "confidence_sum": 0.0})
            total = bucket["total"]
            avg = round(bucket["confidence_sum"] / total, 3) if total else 0.0
            field_cells.append(
                {
                    "field_key": field_key,
                    "label": FIELD_SPEC[field_key]["label"],
                    "total": total,
                    "missing": bucket["missing"],
                    "low": bucket["low"],
                    "avg_confidence": avg,
                    "miss_rate": round(bucket["missing"] / total, 3) if total else 0.0,
                }
            )
            totals = field_totals[field_key]
            totals["total"] += total
            totals["missing"] += bucket["missing"]
            totals["low"] += bucket["low"]
            totals["confidence_sum"] += bucket["confidence_sum"]
        site_rows.append(
            {
                "site_id": site_id,
                "site_name": site.name,
                "site_domain": site.domain,
                "region": site.region,
                "cells": field_cells,
            }
        )
    overall = []
    for field_key in FIELD_ORDER:
        totals = field_totals[field_key]
        total = totals["total"]
        overall.append(
            {
                "field_key": field_key,
                "label": FIELD_SPEC[field_key]["label"],
                "total": total,
                "missing": totals["missing"],
                "low": totals["low"],
                "miss_rate": round(totals["missing"] / total, 3) if total else 0.0,
                "avg_confidence": round(totals["confidence_sum"] / total, 3) if total else 0.0,
            }
        )
    return {"sites": site_rows, "overall": overall, "threshold": settings.low_confidence_threshold}


def _set_reviewed(field: ExtractedField, reviewer: str, status: str) -> None:
    field.status = status
    field.reviewer = reviewer
    field.reviewed_at = now_local()


def correct_field(db: Session, field_id: int, payload: dict, reviewer: str) -> dict:
    field = get_field(db, field_id)
    raw_value = (payload.get("value") or "").strip()
    if not raw_value:
        raise AppError("VALIDATION", 422, detail="value 不能为空")
    if len(raw_value) > MAX_FIELD_VALUE_LENGTH:
        raise AppError("VALIDATION", 422, detail=f"value 超过 {MAX_FIELD_VALUE_LENGTH} 字符")
    note = (payload.get("note") or "").strip()
    notice = db.get(Notice, field.notice_id)
    previous = field.value_text
    if field.field_key == "budget_amount":
        amount_yuan, unit, normalized = extraction_engine.parse_amount_text(raw_value, payload.get("unit"))
        if amount_yuan is None:
            raise AppError("VALIDATION", 422, detail="无法从修正值解析出金额（需带万元/元等单位）")
        field.value_text = normalized if payload.get("unit") else raw_value
        field.unit = unit
        field.amount_yuan = amount_yuan
        field.precision = "absolute"
        field.is_estimated = False
    elif field.field_key == "deadline":
        event_at, precision, estimated = extraction_engine.parse_deadline_text(
            raw_value, notice.published_at if notice else None
        )
        if event_at is None:
            raise AppError("VALIDATION", 422, detail="无法从修正值解析出日期")
        field.value_text = raw_value
        field.event_at = event_at
        field.precision = precision
        field.is_estimated = estimated
    else:
        field.value_text = raw_value
    field.reason = f"{field.reason}｜人工修正（{reviewer}）：{previous or '空'} → {field.value_text}"[:400]
    _set_reviewed(field, reviewer, FieldStatus.CORRECTED.value)
    db.flush()
    event = None
    if field.field_key == "deadline" and notice is not None and notice.status == NoticeStatus.TRACKING.value:
        event = deadline_service.sync_from_field(db, field)
    elif field.field_key == "budget_amount" and notice is not None:
        db.flush()
    return {
        "field": serialize_field(db, field, notice),
        "previous_value": previous,
        "note": note,
        "deadline_event": None
        if event is None
        else {
            "id": event.id,
            "event_at": iso_local(event.event_at),
            "risk_level": event.risk_level,
            "risk_score": event.risk_score,
            "deadline_pressure": event.deadline_pressure,
        },
    }


def verify_field(db: Session, field_id: int, reviewer: str) -> dict:
    field = get_field(db, field_id)
    if field.value_text is None:
        raise AppError("VALIDATION", 422, detail="空值字段不能直接通过，请先修正")
    _set_reviewed(field, reviewer, FieldStatus.VERIFIED.value)
    db.flush()
    return {"field": serialize_field(db, field)}


def reject_field(db: Session, field_id: int, reviewer: str, note: str | None = None) -> dict:
    field = get_field(db, field_id)
    _set_reviewed(field, reviewer, FieldStatus.REJECTED.value)
    if note:
        field.reason = f"{field.reason}｜驳回：{note}"[:400]
    db.flush()
    return {"field": serialize_field(db, field)}


def stats(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(ExtractedField)) or 0
    low = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .where(ExtractedField.confidence < settings.low_confidence_threshold)
    ) or 0
    pending = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .where(
            ExtractedField.confidence < settings.low_confidence_threshold,
            ExtractedField.status == FieldStatus.EXTRACTED.value,
        )
    ) or 0
    reviewed = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .where(ExtractedField.status.in_([FieldStatus.VERIFIED.value, FieldStatus.CORRECTED.value]))
    ) or 0
    missing = db.scalar(
        select(func.count()).select_from(ExtractedField).where(ExtractedField.value_text.is_(None))
    ) or 0
    avg = db.scalar(select(func.avg(ExtractedField.confidence))) or 0.0
    return {
        "total": total,
        "low_confidence": low,
        "pending": pending,
        "reviewed": reviewed,
        "missing": missing,
        "avg_confidence": round(float(avg), 3),
        "threshold": settings.low_confidence_threshold,
    }


def as_datetime(value: datetime | None) -> datetime | None:
    return value


def budget_display(amount_yuan: float | None) -> str:
    if not amount_yuan:
        return "—"
    return f"{comma_number(amount_yuan / 10000, 2)} 万元"
