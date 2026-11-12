"""报表：总览指标 / 本周必投名单 CSV / 审计日志。"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import INDUSTRIES, RiskLevel
from src.models.crawl_run import CrawlRun
from src.models.deadline_event import DeadlineEvent
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.services import audit_service, deadline_service, field_service
from src.utils.timeutil import iso_local, week_start

CSV_HEADERS = [
    "登记号",
    "公告标题",
    "采源区域",
    "公告分类",
    "所属行业",
    "预算(万元)",
    "截止类型",
    "截止时间",
    "剩余工作时长(h)",
    "截止压力",
    "资质要求",
    "资质差距",
    "风险分",
    "风险档位",
    "建议动作",
]


def overview(db: Session) -> dict:
    notice_count = db.scalar(select(func.count()).select_from(Notice)) or 0
    site_count = db.scalar(select(func.count()).select_from(Site)) or 0
    run_count = db.scalar(select(func.count()).select_from(CrawlRun)) or 0
    event_count = db.scalar(select(func.count()).select_from(DeadlineEvent)) or 0
    fields = field_service.stats(db)
    risk_rows = db.execute(
        select(DeadlineEvent.risk_level, func.count()).group_by(DeadlineEvent.risk_level)
    ).all()
    risk_counts = {level.value: 0 for level in RiskLevel}
    for level, count in risk_rows:
        risk_counts[level] = count
    budget_total = db.scalar(
        select(func.sum(ExtractedField.amount_yuan)).where(
            ExtractedField.field_key == "budget_amount",
            ExtractedField.amount_yuan.is_not(None),
        )
    ) or 0.0
    latest_run = db.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()))
    return {
        "notice_count": notice_count,
        "site_count": site_count,
        "run_count": run_count,
        "event_count": event_count,
        "field_total": fields["total"],
        "field_low_confidence": fields["low_confidence"],
        "review_pending": fields["pending"],
        "reviewed": fields["reviewed"],
        "missing_fields": fields["missing"],
        "avg_confidence": fields["avg_confidence"],
        "low_confidence_threshold": settings.low_confidence_threshold,
        "risk_counts": risk_counts,
        "budget_total_wan": round(float(budget_total) / 10000, 2),
        "latest_run": None
        if latest_run is None
        else {
            "id": latest_run.id,
            "status": latest_run.status,
            "fetched_count": latest_run.fetched_count,
            "inserted_count": latest_run.inserted_count,
            "duplicate_count": latest_run.duplicate_count,
            "field_count": latest_run.field_count,
            "low_confidence_count": latest_run.low_confidence_count,
            "duration_ms": latest_run.duration_ms,
            "finished_at": iso_local(latest_run.finished_at),
        },
    }


def weekly_rows(db: Session, as_of: datetime | None = None, industry: str | None = None) -> list[dict]:
    return deadline_service.week_must_bid_rows(db, as_of=as_of, industry=industry)


def weekly_csv(db: Session, as_of: datetime | None = None, industry: str | None = None) -> tuple[str, str]:
    as_of = as_of or deadline_service.demo_as_of()
    rows = weekly_rows(db, as_of=as_of, industry=industry)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                row["external_id"],
                row["title"],
                row["region"],
                row["category"],
                row["industry"],
                "" if row["budget_wan"] is None else f"{row['budget_wan']:.2f}",
                "报名截止" if row["event_kind"] == "enroll" else "开标",
                row["event_at"],
                "" if row["work_hours_remaining"] is None else f"{row['work_hours_remaining']:.2f}",
                "" if row["deadline_pressure"] is None else f"{row['deadline_pressure']:.3f}",
                row["qualification_label"],
                "" if row["qualify_gap"] is None else f"{row['qualify_gap']:.2f}",
                "" if row["risk_score"] is None else f"{row['risk_score']:.1f}",
                row["risk_label"],
                row["action"],
            ]
        )
    content = "\ufeff" + buffer.getvalue()
    scope = industry or "all"
    filename = f"bidsift-week-{week_start(as_of).strftime('%Y%m%d')}-{scope}.csv"
    return filename, content


def audit_logs(db: Session, limit: int = 60) -> list[dict]:
    return audit_service.list_logs(db, limit=limit)


def industry_options() -> list[str]:
    return list(INDUSTRIES)
