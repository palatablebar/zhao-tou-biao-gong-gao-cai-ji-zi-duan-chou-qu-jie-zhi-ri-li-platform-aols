"""抽取模板：版本管理 / 生效版本取用 / 版本对比。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import FIELD_ORDER, FieldKey, TemplateStatus
from src.constants.fieldspec import FIELD_SPEC
from src.constants.limits import MAX_TEMPLATE_RULES
from src.models.site import Site
from src.models.template import ExtractionTemplate
from src.utils.errors import AppError
from src.utils.timeutil import iso_local, now_local


def default_rules() -> dict:
    rules: dict = {}
    for field_key in FIELD_ORDER:
        spec = FIELD_SPEC[field_key]
        rules[field_key] = {
            "label": spec["label"],
            "anchors": list(spec["anchors"]),
            "patterns": list(spec["patterns"]),
        }
    return rules


def normalize_rules(raw: dict | None) -> dict:
    if not raw:
        return default_rules()
    rules = default_rules()
    unknown = [key for key in raw if key not in FIELD_ORDER]
    if unknown:
        raise AppError("VALIDATION", 422, detail=f"未知字段：{','.join(unknown)}")
    total_anchors = 0
    for field_key, spec in raw.items():
        if not isinstance(spec, dict):
            raise AppError("VALIDATION", 422, detail=f"{field_key} 规则必须是对象")
        anchors = spec.get("anchors")
        if anchors is not None:
            if not isinstance(anchors, list) or not all(isinstance(item, str) for item in anchors):
                raise AppError("VALIDATION", 422, detail=f"{field_key}.anchors 必须是字符串数组")
            cleaned = [item.strip() for item in anchors if item.strip()]
            if not cleaned or len(cleaned) > 12:
                raise AppError("VALIDATION", 422, detail=f"{field_key}.anchors 数量须为 1-12")
            rules[field_key]["anchors"] = cleaned
            total_anchors += len(cleaned)
        patterns = spec.get("patterns")
        if patterns is not None:
            if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
                raise AppError("VALIDATION", 422, detail=f"{field_key}.patterns 必须是字符串数组")
            rules[field_key]["patterns"] = [item for item in patterns if item.strip()]
    if total_anchors > MAX_TEMPLATE_RULES:
        raise AppError("VALIDATION", 422, detail=f"锚点总数超过 {MAX_TEMPLATE_RULES}")
    return rules


def serialize_template(db: Session, template: ExtractionTemplate) -> dict:
    site = db.get(Site, template.site_id)
    return {
        "id": template.id,
        "site_id": template.site_id,
        "site_name": site.name if site else "",
        "site_domain": site.domain if site else "",
        "name": template.name,
        "version": template.version,
        "status": template.status,
        "field_rules": template.field_rules,
        "coverage_score": template.coverage_score,
        "change_note": template.change_note,
        "created_by": template.created_by,
        "created_at": iso_local(template.created_at),
        "published_at": iso_local(template.published_at),
    }


def list_templates(db: Session, site_id: int | None = None) -> list[dict]:
    stmt = select(ExtractionTemplate).order_by(ExtractionTemplate.site_id, ExtractionTemplate.version.desc())
    if site_id:
        stmt = stmt.where(ExtractionTemplate.site_id == site_id)
    templates = db.scalars(stmt).all()
    return [serialize_template(db, template) for template in templates]


def active_template(db: Session, site_id: int) -> ExtractionTemplate | None:
    return db.scalar(
        select(ExtractionTemplate).where(
            ExtractionTemplate.site_id == site_id,
            ExtractionTemplate.status == TemplateStatus.ACTIVE.value,
        )
    )


def anchors_for_site(db: Session, site_id: int) -> dict[str, list[str]] | None:
    template = active_template(db, site_id)
    if template is None or not template.field_rules:
        return None
    anchors: dict[str, list[str]] = {}
    for field_key in FIELD_ORDER:
        spec = template.field_rules.get(field_key) or {}
        values = spec.get("anchors")
        if isinstance(values, list) and values:
            anchors[field_key] = [str(item) for item in values]
    return anchors or None


def create_template(db: Session, payload: dict, actor_email: str) -> dict:
    site_id = payload.get("site_id")
    name = (payload.get("name") or "").strip()
    if not site_id or not name:
        raise AppError("VALIDATION", 422, detail="site_id 与 name 必填")
    site = db.get(Site, int(site_id))
    if site is None:
        raise AppError("NOT_FOUND", 404, detail=f"site_id={site_id}")
    rules = normalize_rules(payload.get("field_rules"))
    max_version = db.scalar(
        select(func.max(ExtractionTemplate.version)).where(
            ExtractionTemplate.site_id == site.id, ExtractionTemplate.name == name
        )
    ) or 0
    template = ExtractionTemplate(
        site_id=site.id,
        name=name,
        version=max_version + 1,
        status=TemplateStatus.DRAFT.value,
        field_rules=rules,
        coverage_score=float(payload.get("coverage_score") or 0.0),
        change_note=(payload.get("change_note") or "").strip() or None,
        created_by=actor_email,
    )
    db.add(template)
    db.flush()
    return serialize_template(db, template)


def publish_template(db: Session, template_id: int, actor_email: str) -> dict:
    template = db.get(ExtractionTemplate, template_id)
    if template is None:
        raise AppError("NOT_FOUND", 404, detail=f"template_id={template_id}")
    if template.status == TemplateStatus.ACTIVE.value:
        raise AppError("TEMPLATE_STATE", 409, detail="该版本已是生效版本")
    others = db.scalars(
        select(ExtractionTemplate).where(
            ExtractionTemplate.site_id == template.site_id,
            ExtractionTemplate.name == template.name,
            ExtractionTemplate.status == TemplateStatus.ACTIVE.value,
        )
    ).all()
    for other in others:
        other.status = TemplateStatus.ARCHIVED.value
    template.status = TemplateStatus.ACTIVE.value
    template.published_at = now_local()
    db.flush()
    return {"template": serialize_template(db, template), "archived": [item.id for item in others]}


def compare_templates(db: Session, left_id: int, right_id: int) -> dict:
    left = db.get(ExtractionTemplate, left_id)
    right = db.get(ExtractionTemplate, right_id)
    if left is None or right is None:
        raise AppError("NOT_FOUND", 404, detail="版本不存在")
    if left.site_id != right.site_id:
        raise AppError("VALIDATION", 422, detail="只能对比同一站点的模板版本")
    diffs: list[dict] = []
    for field_key in FIELD_ORDER:
        left_rule = (left.field_rules or {}).get(field_key) or {}
        right_rule = (right.field_rules or {}).get(field_key) or {}
        left_anchors = list(left_rule.get("anchors") or [])
        right_anchors = list(right_rule.get("anchors") or [])
        added = [item for item in right_anchors if item not in left_anchors]
        removed = [item for item in left_anchors if item not in right_anchors]
        left_patterns = list(left_rule.get("patterns") or [])
        right_patterns = list(right_rule.get("patterns") or [])
        pattern_changed = left_patterns != right_patterns
        diffs.append(
            {
                "field_key": field_key,
                "label": FIELD_SPEC[field_key]["label"],
                "anchors_added": added,
                "anchors_removed": removed,
                "pattern_changed": pattern_changed,
                "left_anchor_count": len(left_anchors),
                "right_anchor_count": len(right_anchors),
                "changed": bool(added or removed or pattern_changed),
            }
        )
    return {
        "left": serialize_template(db, left),
        "right": serialize_template(db, right),
        "coverage_delta": round((right.coverage_score or 0) - (left.coverage_score or 0), 3),
        "changed_field_count": sum(1 for item in diffs if item["changed"]),
        "diffs": diffs,
    }


def upsert_version(
    db: Session,
    *,
    site_id: int,
    name: str,
    version: int,
    status: str,
    rules: dict,
    coverage: float,
    change_note: str,
    created_by: str,
    published_at=None,
) -> ExtractionTemplate:
    template = db.scalar(
        select(ExtractionTemplate).where(
            ExtractionTemplate.site_id == site_id,
            ExtractionTemplate.name == name,
            ExtractionTemplate.version == version,
        )
    )
    if template is None:
        template = ExtractionTemplate(
            site_id=site_id,
            name=name,
            version=version,
            status=status,
            field_rules=rules,
            coverage_score=coverage,
            change_note=change_note,
            created_by=created_by,
            published_at=published_at,
        )
        db.add(template)
        db.flush()
    return template
