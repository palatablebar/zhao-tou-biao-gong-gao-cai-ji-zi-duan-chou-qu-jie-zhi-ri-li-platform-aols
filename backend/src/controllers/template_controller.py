"""抽取模板控制器（版本创建 / 发布预演 / 发布切换 / 对比）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, deadline_service, publish_service, template_service


def list_templates(db: Session, site_id: int | None = None) -> dict:
    return {
        "items": template_service.list_templates(db, site_id=site_id),
        "default_rules": template_service.default_rules(),
    }


def create_template(db: Session, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    template = template_service.create_template(db, payload, actor_email)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="template.create",
        entity="template",
        entity_id=template["id"],
        detail={"site_id": template["site_id"], "version": template["version"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {"template": template}


def preview_publish(db: Session, template_id: int, as_of: str | None = None) -> dict:
    """发布前试算：按新规则重算该采源历史公告，返回影响面但不落库。"""
    resolved = deadline_service.resolve_as_of(as_of)
    return publish_service.preview_publish(db, template_id, as_of=resolved)


def publish_template(
    db: Session,
    template_id: int,
    actor_email: str,
    actor_role: str,
    request: Request,
    as_of: str | None = None,
) -> dict:
    resolved = deadline_service.resolve_as_of(as_of)
    try:
        result = publish_service.publish_template(
            db, template_id, actor_email, as_of=resolved
        )
    except Exception:
        # 重算或切换任一步失败：整批回滚，上一版继续生效
        db.rollback()
        raise
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="template.publish",
        entity="template",
        entity_id=template_id,
        detail={
            "version": result["template"]["version"],
            "site_id": result["site"]["id"],
            "noop": result.get("noop", False),
            "archived": result["archived"],
            "affected_notice_count": result["affected_notice_count"],
            "field_updated": result["field_summary"]["updated"],
            "field_preserved": result["field_summary"]["preserved_manual"],
            "pending_date_count": result["deadline_summary"]["pending_date_count"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def compare_templates(db: Session, left_id: int, right_id: int) -> dict:
    return template_service.compare_templates(db, left_id, right_id)
