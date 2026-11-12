"""模板发布：按新规则重算该采源历史公告的抽取字段与截止风险，全部成功后再切换生效版本。

口径：
- 只影响该模板所属采源（site）的公告，不触碰其他交易中心；
- 先预演（preview）给出影响公告 / 字段变化 / 待补日期，不写库；
- 正式发布在同一事务内「重算字段 → 重算截止风险 → 归档旧版 → 激活新版」，任一步失败整体回滚，
  旧版本保持生效，库内不会出现新旧规则混杂的中间态；
- 人工修正（corrected）与人工通过（verified）的字段原样保留，连同其截止事件不再被模板覆盖；
- 字段按 (notice_id, field_key)、事件按 (notice_id, kind) 原地更新，重复执行不新增记录；
- 预演只读、应用幂等，失败后重试会从上一版干净状态重新开始。
"""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import FIELD_ORDER, DeadlineKind, FieldStatus, TemplateStatus
from src.constants.fieldspec import FIELD_SPEC
from src.models.deadline_event import DeadlineEvent
from src.models.extracted_field import ExtractedField
from src.models.notice import Notice
from src.models.site import Site
from src.models.template import ExtractionTemplate
from src.services import deadline_service, extraction_engine, field_service
from src.services.deadline_service import SCORE_FIELDS, score_values
from src.utils.errors import AppError
from src.utils.timeutil import iso_local, now_local

# 明细列表一次最多回传多少条，避免大采源把响应撑爆（汇总计数不受影响）
MAX_DETAIL_ROWS = 200

PRESERVED_STATUSES = (FieldStatus.VERIFIED.value, FieldStatus.CORRECTED.value)


@dataclass
class FieldPlan:
    notice: Notice
    field_key: str
    action: str  # create / update / unchanged / preserve
    result: dict
    existing: ExtractedField | None = None
    changed_value: bool = False
    status_before: str | None = None
    status_after: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    old_confidence: float | None = None
    new_confidence: float | None = None


@dataclass
class EventPlan:
    notice: Notice
    event: DeadlineEvent
    event_at: datetime | None
    precision: str
    values: dict
    changed: bool = False
    event_at_changed: bool = False
    risk_changed: bool = False


@dataclass
class PublishPlan:
    template: ExtractionTemplate
    previous: ExtractionTemplate | None
    site: Site
    as_of: datetime
    notice_count: int = 0
    fields: list[FieldPlan] = dataclass_field(default_factory=list)
    events: list[EventPlan] = dataclass_field(default_factory=list)
    risk_before: dict[str, int] = dataclass_field(default_factory=dict)


# ---------------------------------------------------------------- helpers


def _rules_anchors(rules: dict) -> dict[str, list[str]]:
    anchors: dict[str, list[str]] = {}
    for field_key in FIELD_ORDER:
        spec = (rules or {}).get(field_key) or {}
        values = spec.get("anchors")
        if isinstance(values, list) and values:
            anchors[field_key] = [str(item) for item in values]
        else:
            anchors[field_key] = list(FIELD_SPEC[field_key]["anchors"])
    return anchors


def _field_signature_from_result(result: dict) -> tuple:
    return (
        result.get("value_text"),
        result.get("raw_text"),
        result.get("unit"),
        result.get("amount_yuan"),
        result.get("event_at"),
        result.get("precision"),
        bool(result.get("is_estimated")),
        float(result.get("anchor_score") or 0.0),
        float(result.get("format_score") or 0.0),
        float(result.get("clarity_score") or 0.0),
        float(result.get("confidence") or 0.0),
        result.get("reason") or "",
    )


def _field_signature(field: ExtractedField) -> tuple:
    return (
        field.value_text,
        field.raw_text,
        field.unit,
        field.amount_yuan,
        field.event_at,
        field.precision,
        bool(field.is_estimated),
        float(field.anchor_score or 0.0),
        float(field.format_score or 0.0),
        float(field.clarity_score or 0.0),
        float(field.confidence or 0.0),
        field.reason or "",
    )


def _event_signature(event: DeadlineEvent) -> tuple:
    return (
        event.event_at,
        event.precision,
        event.work_hours_remaining,
        event.deadline_pressure,
        event.qualify_gap,
        event.risk_score,
        event.risk_level,
    )


def _next_event_signature(plan: EventPlan) -> tuple:
    values = plan.values
    return (
        plan.event_at,
        plan.precision,
        values.get("work_hours_remaining"),
        values.get("deadline_pressure"),
        values.get("qualify_gap"),
        values.get("risk_score"),
        values.get("risk_level"),
    )


def _load_fields(db: Session, notice_ids: list[int]) -> dict[int, dict[str, ExtractedField]]:
    if not notice_ids:
        return {}
    rows = db.scalars(select(ExtractedField).where(ExtractedField.notice_id.in_(notice_ids))).all()
    grouped: dict[int, dict[str, ExtractedField]] = {}
    for row in rows:
        grouped.setdefault(row.notice_id, {})[row.field_key] = row
    return grouped


def _load_events(db: Session, notice_ids: list[int]) -> dict[int, list[DeadlineEvent]]:
    if not notice_ids:
        return {}
    rows = db.scalars(select(DeadlineEvent).where(DeadlineEvent.notice_id.in_(notice_ids))).all()
    grouped: dict[int, list[DeadlineEvent]] = {}
    for row in rows:
        grouped.setdefault(row.notice_id, []).append(row)
    return grouped


# ---------------------------------------------------------------- plan


def build_plan(
    db: Session,
    template: ExtractionTemplate,
    as_of: datetime,
    *,
    previous: ExtractionTemplate | None = None,
) -> PublishPlan:
    """只读预演：生成字段 / 事件的变更计划，不修改任何持久化对象。"""
    site = db.get(Site, template.site_id)
    if site is None:
        raise AppError("NOT_FOUND", 404, detail=f"site_id={template.site_id}")

    notices = db.scalars(
        select(Notice).where(Notice.site_id == template.site_id).order_by(Notice.id)
    ).all()
    fields_map = _load_fields(db, [notice.id for notice in notices])
    events_map = _load_events(db, [notice.id for notice in notices])
    anchors = _rules_anchors(template.field_rules or {})

    plan = PublishPlan(
        template=template,
        previous=previous,
        site=site,
        as_of=as_of,
        notice_count=len(notices),
        risk_before={},
    )
    for event in (item for rows in events_map.values() for item in rows):
        plan.risk_before[event.risk_level] = plan.risk_before.get(event.risk_level, 0) + 1

    for notice in notices:
        existing_fields = fields_map.get(notice.id, {})
        try:
            results = extraction_engine.extract_notice(
                notice.clean_text, notice.published_at, anchors
            )
        except Exception as exc:  # noqa: BLE001 - 预演失败要明确告诉调用方
            raise AppError(
                "PUBLISH_FAILED",
                409,
                detail=f"公告 {notice.external_id} 抽取失败：{exc}",
            ) from exc

        deadline_plan: FieldPlan | None = None
        for field_key in FIELD_ORDER:
            result = results[field_key]
            existing = existing_fields.get(field_key)
            plan.fields.append(_plan_field(notice, field_key, result, existing))
            if field_key == "deadline":
                deadline_plan = plan.fields[-1]

        for event in events_map.get(notice.id, []):
            plan.events.append(_plan_event(notice, event, deadline_plan, as_of))

    return plan


def _plan_field(
    notice: Notice,
    field_key: str,
    result: dict,
    existing: ExtractedField | None,
) -> FieldPlan:
    if existing is None:
        return FieldPlan(
            notice=notice,
            field_key=field_key,
            action="create",
            result=result,
            changed_value=result.get("value_text") is not None,
            status_before=None,
            status_after=FieldStatus.EXTRACTED.value,
            old_value=None,
            new_value=result.get("value_text"),
            old_confidence=None,
            new_confidence=float(result.get("confidence") or 0.0),
        )

    if existing.status in PRESERVED_STATUSES:
        return FieldPlan(
            notice=notice,
            field_key=field_key,
            action="preserve",
            result=result,
            existing=existing,
            changed_value=False,
            status_before=existing.status,
            status_after=existing.status,
            old_value=existing.value_text,
            new_value=existing.value_text,
            old_confidence=existing.confidence,
            new_confidence=existing.confidence,
        )

    changed = _field_signature(existing) != _field_signature_from_result(result)
    # 驳回字段在新规则下重新抽取后回到待复核，避免旧结论压住新结果
    reset = existing.status == FieldStatus.REJECTED.value
    return FieldPlan(
        notice=notice,
        field_key=field_key,
        action="update" if (changed or reset) else "unchanged",
        result=result,
        existing=existing,
        changed_value=changed,
        status_before=existing.status,
        status_after=FieldStatus.EXTRACTED.value if reset else existing.status,
        old_value=existing.value_text,
        new_value=result.get("value_text") if (changed or reset) else existing.value_text,
        old_confidence=existing.confidence,
        new_confidence=float(result.get("confidence") or 0.0) if (changed or reset) else existing.confidence,
    )


def _plan_event(
    notice: Notice,
    event: DeadlineEvent,
    deadline_plan: FieldPlan | None,
    as_of: datetime,
) -> EventPlan:
    event_at = event.event_at
    precision = event.precision
    if (
        event.kind == DeadlineKind.ENROLL.value
        and deadline_plan is not None
        and deadline_plan.action != "preserve"
    ):
        # 报名截止事件跟随新规则下的抽取结果；新规则抽不到日期时落到「待补日期」，
        # 人工修正/通过的字段则连同其日历事件一起保留。
        event_at = deadline_plan.result.get("event_at")
        precision = deadline_plan.result.get("precision") or "missing"

    values = score_values(event_at, notice.qualification, as_of)
    plan = EventPlan(
        notice=notice,
        event=event,
        event_at=event_at,
        precision=precision,
        values=values,
    )
    plan.event_at_changed = event_at != event.event_at
    plan.risk_changed = event.risk_level != values["risk_level"]
    plan.changed = plan.event_at_changed or _event_signature(event) != _next_event_signature(plan)
    return plan


# ---------------------------------------------------------------- summary


def summarize_plan(plan: PublishPlan, *, applied: bool) -> dict:
    by_field: dict[str, dict] = {
        key: {
            "field_key": key,
            "label": FIELD_SPEC[key]["label"],
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "preserved": 0,
            "changed_value": 0,
        }
        for key in FIELD_ORDER
    }
    field_changes: list[dict] = []
    affected_notices: set[int] = set()
    created = updated = unchanged = preserved = changed_values = 0

    for item in plan.fields:
        bucket = by_field[item.field_key]
        if item.action == "create":
            created += 1
            bucket["created"] += 1
            if item.changed_value:
                changed_values += 1
                bucket["changed_value"] += 1
                affected_notices.add(item.notice.id)
        elif item.action == "update":
            updated += 1
            bucket["updated"] += 1
            if item.changed_value:
                changed_values += 1
                bucket["changed_value"] += 1
            if item.changed_value or item.status_before != item.status_after:
                affected_notices.add(item.notice.id)
        elif item.action == "unchanged":
            unchanged += 1
            bucket["unchanged"] += 1
        else:
            preserved += 1
            bucket["preserved"] += 1

        if item.action in ("create", "update") and (item.changed_value or item.status_before != item.status_after):
            field_changes.append(
                {
                    "notice_id": item.notice.id,
                    "external_id": item.notice.external_id,
                    "title": item.notice.title,
                    "field_key": item.field_key,
                    "label": FIELD_SPEC[item.field_key]["label"],
                    "action": item.action,
                    "status_before": item.status_before,
                    "status_after": item.status_after,
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                    "old_confidence": item.old_confidence,
                    "new_confidence": item.new_confidence,
                }
            )

    risk_after: dict[str, int] = {}
    pending_dates: list[dict] = []
    event_at_changed = risk_changed = rescored = 0
    for item in plan.events:
        risk_after[item.values["risk_level"]] = risk_after.get(item.values["risk_level"], 0) + 1
        if item.changed:
            rescored += 1
            affected_notices.add(item.notice.id)
        if item.event_at_changed:
            event_at_changed += 1
        if item.risk_changed:
            risk_changed += 1
        if item.event_at is None:
            pending_dates.append(
                {
                    "notice_id": item.notice.id,
                    "external_id": item.notice.external_id,
                    "title": item.notice.title,
                    "kind": item.event.kind,
                    "reason": item.values["note"],
                }
            )

    detail_truncated = len(field_changes) > MAX_DETAIL_ROWS
    return {
        "applied": applied,
        "as_of": iso_local(plan.as_of),
        "site": {"id": plan.site.id, "name": plan.site.name, "domain": plan.site.domain},
        "template": {
            "id": plan.template.id,
            "name": plan.template.name,
            "version": plan.template.version,
            "status": plan.template.status,
        },
        "previous": None
        if plan.previous is None
        else {
            "id": plan.previous.id,
            "name": plan.previous.name,
            "version": plan.previous.version,
        },
        "notice_count": plan.notice_count,
        "affected_notice_count": len(affected_notices),
        "field_summary": {
            "total": len(plan.fields),
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "preserved_manual": preserved,
            "changed_value": changed_values,
            "by_field": list(by_field.values()),
        },
        "field_changes": field_changes[:MAX_DETAIL_ROWS],
        "field_changes_truncated": detail_truncated,
        "deadline_summary": {
            "event_count": len(plan.events),
            "rescored": rescored,
            "event_at_changed": event_at_changed,
            "risk_changed": risk_changed,
            "pending_date_count": len(pending_dates),
            "risk_before": plan.risk_before,
            "risk_after": risk_after,
        },
        "pending_dates": pending_dates[:MAX_DETAIL_ROWS],
        "pending_dates_truncated": len(pending_dates) > MAX_DETAIL_ROWS,
    }


# ---------------------------------------------------------------- apply


def apply_plan(db: Session, plan: PublishPlan) -> None:
    """把计划写入当前事务；调用方负责 commit / rollback。"""
    for item in plan.fields:
        if item.action == "create":
            field = ExtractedField(notice_id=item.notice.id, field_key=item.field_key)
            field_service.apply_result(field, item.result)
            db.add(field)
        elif item.action == "update":
            field = item.existing
            if field is None:
                continue
            field_service.apply_result(field, item.result)
            if item.status_before == FieldStatus.REJECTED.value:
                field.status = FieldStatus.EXTRACTED.value
                field.reviewer = None
                field.reviewed_at = None
        # unchanged / preserve 不落写，重复发布不会刷新 extracted_at 或覆盖人工值

    for item in plan.events:
        if not item.changed:
            continue
        event = item.event
        event.event_at = item.event_at
        event.precision = item.precision
        for key in SCORE_FIELDS:
            setattr(event, key, item.values[key])
        event.computed_at = plan.as_of
    db.flush()


# ---------------------------------------------------------------- entrypoints


def preview_publish(db: Session, template_id: int, as_of: datetime | None = None) -> dict:
    template = db.get(ExtractionTemplate, template_id)
    if template is None:
        raise AppError("NOT_FOUND", 404, detail=f"template_id={template_id}")
    previous = _active_for_site(db, template.site_id, exclude_id=template.id)
    plan = build_plan(
        db,
        template,
        as_of or deadline_service.demo_as_of(),
        previous=previous,
    )
    return summarize_plan(plan, applied=False)


def publish_template(
    db: Session,
    template_id: int,
    actor_email: str,
    as_of: datetime | None = None,
) -> dict:
    """同一事务内重算 + 切换；失败抛错由调用方 rollback，旧版本保持生效。

    幂等：对已生效版本再次发布返回当前状态（applied=False / noop=True），不重算、不新增记录。
    """
    resolved_as_of = as_of or deadline_service.demo_as_of()
    # 锁住目标版本，避免两个发布操作同时改同一版本
    template = db.scalar(
        select(ExtractionTemplate).where(ExtractionTemplate.id == template_id).with_for_update()
    )
    if template is None:
        raise AppError("NOT_FOUND", 404, detail=f"template_id={template_id}")
    if template.status == TemplateStatus.ACTIVE.value:
        previous = _active_for_site(db, template.site_id, exclude_id=template.id)
        plan = build_plan(db, template, resolved_as_of, previous=previous)
        summary = summarize_plan(plan, applied=False)
        summary.update({"noop": True, "archived": []})
        summary["template"]["status"] = template.status
        return summary

    previous = _active_for_site(db, template.site_id, exclude_id=template.id)
    plan = build_plan(db, template, resolved_as_of, previous=previous)
    summary = summarize_plan(plan, applied=True)
    try:
        apply_plan(db, plan)
        archived = _archive_site_active(db, template)
        template.status = TemplateStatus.ACTIVE.value
        template.published_at = now_local()
        db.flush()
    except Exception as exc:  # noqa: BLE001 - 转换统一业务错误，事务由调用方回滚
        raise AppError(
            "PUBLISH_FAILED",
            409,
            detail=f"重算或切换失败，已保留上一版：{exc}",
        ) from exc

    summary.update({"noop": False, "archived": [item.id for item in archived]})
    summary["template"]["status"] = template.status
    return summary


def _active_for_site(
    db: Session, site_id: int, exclude_id: int | None = None
) -> ExtractionTemplate | None:
    stmt = select(ExtractionTemplate).where(
        ExtractionTemplate.site_id == site_id,
        ExtractionTemplate.status == TemplateStatus.ACTIVE.value,
    )
    if exclude_id is not None:
        stmt = stmt.where(ExtractionTemplate.id != exclude_id)
    return db.scalars(stmt.order_by(ExtractionTemplate.version.desc())).first()


def _archive_site_active(db: Session, template: ExtractionTemplate) -> list[ExtractionTemplate]:
    stmt = select(ExtractionTemplate).where(
        ExtractionTemplate.site_id == template.site_id,
        ExtractionTemplate.status == TemplateStatus.ACTIVE.value,
        ExtractionTemplate.id != template.id,
    ).with_for_update()
    others = db.scalars(stmt).all()
    for other in others:
        other.status = TemplateStatus.ARCHIVED.value
    return list(others)
