"""算法 2：截止风险评分（工作日历 + 资质差距 + 三档分派），结果落库。

口径（默认评估基准时刻 = 演示基准 2026-11-12 09:00，可用 as_of 覆盖，保证可复现）：
- 剩余工作时长 h：工作日 09:00–18:00，剔除周末与 2026 年法定节假日（简化表）
- deadline_pressure = clamp(1 − h / 72, 0, 1)
- qualify_gap：本公司工程咨询乙级（二级）→ 无/二级 0.0，一级 0.45，特级 0.85
- risk_score = 100 × (0.62 × deadline_pressure + 0.38 × (1 − qualify_gap))
- 分档：gap ≥ 0.5 → skip；pressure ≥ 0.45 → must_act；0.15 ≤ pressure < 0.45 → watch；
  pressure < 0.15 → skip；日期缺失 → unknown（不参与分档）
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import DeadlineKind, NoticeStatus, RiskLevel
from src.constants.fieldspec import (
    QUALIFY_GAP,
    QUAL_LABEL,
    RISK_LABEL,
)
from src.models.deadline_event import DeadlineEvent
from src.models.notice import Notice
from src.services import source_catalog
from src.utils.errors import AppError
from src.utils.textutil import comma_number
from src.utils.timeutil import iso_local, now_local, parse_local
from src.utils.workcalendar import work_hours_between

FORMULA: dict = {
    "deadline_pressure": "clamp(1 − 剩余工作时长 / 72, 0, 1)，工作时段 09:00–18:00，剔除周末与法定节假日",
    "qualify_gap": "无/二级 = 0.00；一级 = 0.45；特级 = 0.85（本公司为工程咨询乙级）",
    "risk_score": "100 × (0.62 × deadline_pressure + 0.38 × (1 − qualify_gap))",
    "must_act": "qualify_gap < 0.5 且 deadline_pressure ≥ 0.45",
    "watch": "qualify_gap < 0.5 且 0.15 ≤ deadline_pressure < 0.45",
    "skip": "qualify_gap ≥ 0.5（资质不够） 或 deadline_pressure < 0.15（时间充裕）",
    "unknown": "事件时刻缺失（原文字段为「另行通知」类占位），不参与分档",
    "horizon_hours": settings.pressure_horizon_hours,
}


def demo_as_of() -> datetime:
    return source_catalog.DEMO_AS_OF


def resolve_as_of(value: str | None) -> datetime:
    """前端可传 as_of 复现某一时刻的评分；缺省用演示基准时刻。"""
    parsed = parse_local(value)
    return parsed or demo_as_of()


def score_event(event: DeadlineEvent, notice: Notice, as_of: datetime) -> None:
    gap = QUALIFY_GAP.get(notice.qualification, 0.0)
    event.qualify_gap = round(gap, 3)
    event.computed_at = as_of
    if event.event_at is None:
        event.work_hours_remaining = None
        event.deadline_pressure = None
        event.risk_score = None
        event.risk_level = RiskLevel.UNKNOWN.value
        event.note = "报名截止时间缺失（原文为「另行通知」类占位），不参与分档，待人工补全"
        return
    hours = work_hours_between(as_of, event.event_at)
    pressure = round(min(1.0, max(0.0, 1.0 - hours / settings.pressure_horizon_hours)), 3)
    score = round(100.0 * (0.62 * pressure + 0.38 * (1.0 - gap)), 1)
    event.work_hours_remaining = hours
    event.deadline_pressure = pressure
    event.risk_score = score
    if gap >= 0.5:
        event.risk_level = RiskLevel.SKIP.value
        event.note = f"资质门槛超出（{QUAL_LABEL.get(notice.qualification, notice.qualification)}），不投标"
    elif pressure >= settings.must_act_pressure:
        event.risk_level = RiskLevel.MUST_ACT.value
        event.note = f"剩余 {hours} 工作小时，需本周报名"
    elif pressure >= settings.watch_pressure:
        event.risk_level = RiskLevel.WATCH.value
        event.note = f"剩余 {hours} 工作小时，保持观察"
    else:
        event.risk_level = RiskLevel.SKIP.value
        event.note = f"剩余 {hours} 工作小时，时间充裕，本周不排"


def recompute_events(db: Session, as_of: datetime | None = None) -> dict:
    as_of = as_of or demo_as_of()
    events = db.scalars(select(DeadlineEvent)).all()
    counts = {level.value: 0 for level in RiskLevel}
    for event in events:
        notice = db.get(Notice, event.notice_id)
        if notice is None:
            continue
        score_event(event, notice, as_of)
        counts[event.risk_level] = counts.get(event.risk_level, 0) + 1
    db.flush()
    return {
        "as_of": iso_local(as_of),
        "total": len(events),
        "counts": counts,
        "formula": FORMULA,
    }


def upsert_event(
    db: Session,
    notice: Notice,
    kind: str,
    event_at: datetime | None,
    precision: str = "absolute",
    seed_key: str | None = None,
) -> DeadlineEvent:
    event = db.scalar(
        select(DeadlineEvent).where(DeadlineEvent.notice_id == notice.id, DeadlineEvent.kind == kind)
    )
    if event is None:
        event = DeadlineEvent(
            notice_id=notice.id,
            kind=kind,
            event_at=event_at,
            precision=precision,
            seed_key=seed_key,
        )
        db.add(event)
        db.flush()
    else:
        event.event_at = event_at or event.event_at
        event.precision = precision
    return event


def ensure_tracked_events(db: Session) -> int:
    """按 18 条跟踪计划补齐日历事件（幂等：notice_id + kind 唯一）。"""
    created = 0
    for item in source_catalog.TRACKED_PLAN:
        payload = source_catalog.build_notice(item["index"])
        notice = db.scalar(select(Notice).where(Notice.external_id == payload["external_id"]))
        if notice is None:
            continue
        existing = db.scalar(
            select(DeadlineEvent).where(
                DeadlineEvent.notice_id == notice.id, DeadlineEvent.kind == item["kind"]
            )
        )
        if existing is None:
            db.add(
                DeadlineEvent(
                    notice_id=notice.id,
                    kind=item["kind"],
                    event_at=item["at"],
                    precision="absolute" if item["at"] else "missing",
                    seed_key=f"deadline:{item['index']:04d}:{item['kind']}",
                )
            )
            created += 1
    db.flush()
    return created


def sync_from_field(db: Session, field) -> DeadlineEvent | None:
    """人工补全/修正报名截止时间后，同步日历事件并重算风险。"""
    notice = db.get(Notice, field.notice_id)
    if notice is None or notice.status != NoticeStatus.TRACKING.value:
        return None
    event = db.scalar(
        select(DeadlineEvent).where(
            DeadlineEvent.notice_id == notice.id, DeadlineEvent.kind == DeadlineKind.ENROLL.value
        )
    )
    if event is None:
        event = upsert_event(db, notice, DeadlineKind.ENROLL.value, field.event_at, field.precision)
    else:
        event.event_at = field.event_at
        event.precision = field.precision
    score_event(event, notice, demo_as_of())
    db.flush()
    return event


def serialize_event(event: DeadlineEvent, notice: Notice) -> dict:
    return {
        "id": event.id,
        "notice_id": notice.id,
        "kind": event.kind,
        "event_at": iso_local(event.event_at),
        "precision": event.precision,
        "work_hours_remaining": event.work_hours_remaining,
        "deadline_pressure": event.deadline_pressure,
        "qualify_gap": event.qualify_gap,
        "risk_score": event.risk_score,
        "risk_level": event.risk_level,
        "risk_label": RISK_LABEL.get(event.risk_level, event.risk_level),
        "note": event.note,
        "computed_at": iso_local(event.computed_at),
        "notice": {
            "id": notice.id,
            "external_id": notice.external_id,
            "title": notice.title,
            "region": notice.region,
            "category": notice.category,
            "industry": notice.industry,
            "qualification": notice.qualification,
            "qualification_label": QUAL_LABEL.get(notice.qualification, notice.qualification),
            "status": notice.status,
            "published_at": iso_local(notice.published_at),
        },
    }


def list_events(db: Session, as_of: datetime | None = None, risk: str | None = None) -> list[dict]:
    as_of = as_of or demo_as_of()
    rows = db.execute(
        select(DeadlineEvent, Notice).join(Notice, Notice.id == DeadlineEvent.notice_id)
    ).all()
    items: list[dict] = []
    for event, notice in rows:
        if risk and event.risk_level != risk:
            continue
        payload = serialize_event(event, notice)
        items.append(payload)
    items.sort(key=lambda item: (item["event_at"] or "9999-12-31", item["id"]))
    return items


def week_must_bid_rows(db: Session, as_of: datetime | None = None, industry: str | None = None) -> list[dict]:
    as_of = as_of or demo_as_of()
    from src.utils.timeutil import week_end, week_start

    start = week_start(as_of)
    end = week_end(as_of)
    rows: list[dict] = []
    for item in list_events(db):
        if item["event_at"] is None or item["risk_level"] != RiskLevel.MUST_ACT.value:
            continue
        event_at = parse_local(item["event_at"])
        if event_at is None or not (start <= event_at < end):
            continue
        if industry and item["notice"]["industry"] != industry:
            continue
        from src.models.extracted_field import ExtractedField

        budget = db.scalar(
            select(ExtractedField).where(
                ExtractedField.notice_id == item["notice_id"],
                ExtractedField.field_key == "budget_amount",
            )
        )
        budget_wan = round((budget.amount_yuan or 0) / 10000, 2) if budget and budget.amount_yuan else None
        rows.append(
            {
                "notice_id": item["notice_id"],
                "external_id": item["notice"]["external_id"],
                "title": item["notice"]["title"],
                "region": item["notice"]["region"],
                "category": item["notice"]["category"],
                "industry": item["notice"]["industry"],
                "qualification_label": item["notice"]["qualification_label"],
                "budget_wan": budget_wan,
                "budget_text": comma_number(budget_wan, 2) if budget_wan else "—",
                "event_kind": item["kind"],
                "event_at": item["event_at"],
                "work_hours_remaining": item["work_hours_remaining"],
                "deadline_pressure": item["deadline_pressure"],
                "qualify_gap": item["qualify_gap"],
                "risk_score": item["risk_score"],
                "risk_level": item["risk_level"],
                "risk_label": item["risk_label"],
                "action": "本周内报名并准备资格预审材料",
            }
        )
    return rows
