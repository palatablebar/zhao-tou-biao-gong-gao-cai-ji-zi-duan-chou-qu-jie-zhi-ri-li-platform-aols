"""采源站点：列表统计 / 配置修改。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import FieldStatus, SiteStatus, TemplateStatus
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.models.template import ExtractionTemplate
from src.utils.errors import AppError
from src.utils.timeutil import iso_local

SITE_UPDATABLE = {"cadence_minutes", "qps_limit", "status", "note"}


def _counts(db: Session, site_id: int) -> dict:
    notice_count = db.scalar(
        select(func.count()).select_from(Notice).where(Notice.site_id == site_id)
    ) or 0
    low_count = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .join(Notice, Notice.id == ExtractedField.notice_id)
        .where(
            Notice.site_id == site_id,
            ExtractedField.confidence < settings.low_confidence_threshold,
            ExtractedField.status == FieldStatus.EXTRACTED.value,
        )
    ) or 0
    field_count = db.scalar(
        select(func.count())
        .select_from(ExtractedField)
        .join(Notice, Notice.id == ExtractedField.notice_id)
        .where(Notice.site_id == site_id)
    ) or 0
    active_templates = db.scalar(
        select(func.count())
        .select_from(ExtractionTemplate)
        .where(
            ExtractionTemplate.site_id == site_id,
            ExtractionTemplate.status == TemplateStatus.ACTIVE.value,
        )
    ) or 0
    return {
        "notice_count": notice_count,
        "field_count": field_count,
        "low_confidence_count": low_count,
        "active_template_count": active_templates,
    }


def serialize_site(db: Session, site: Site) -> dict:
    return {
        "id": site.id,
        "name": site.name,
        "domain": site.domain,
        "region": site.region,
        "cadence_minutes": site.cadence_minutes,
        "qps_limit": site.qps_limit,
        "status": site.status,
        "priority": site.priority,
        "note": site.note,
        "created_at": iso_local(site.created_at),
        **_counts(db, site.id),
    }


def list_sites(db: Session) -> list[dict]:
    sites = db.scalars(select(Site).order_by(Site.priority)).all()
    return [serialize_site(db, site) for site in sites]


def get_site(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise AppError("NOT_FOUND", 404, detail=f"site_id={site_id}")
    return site


def update_site(db: Session, site_id: int, payload: dict) -> dict:
    site = get_site(db, site_id)
    changed: dict = {}
    for key, value in payload.items():
        if key not in SITE_UPDATABLE or value is None:
            continue
        if key == "status" and value not in {status.value for status in SiteStatus}:
            raise AppError("VALIDATION", 422, detail=f"status={value}")
        if key in {"cadence_minutes", "qps_limit"}:
            if not isinstance(value, int) or value <= 0:
                raise AppError("VALIDATION", 422, detail=f"{key} 必须为正整数")
        setattr(site, key, value)
        changed[key] = value
    if not changed:
        raise AppError("VALIDATION", 422, detail="没有可更新的字段")
    db.flush()
    return {"site": serialize_site(db, site), "changed": changed}
