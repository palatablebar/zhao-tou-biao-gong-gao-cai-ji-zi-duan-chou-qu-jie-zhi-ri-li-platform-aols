"""抽取模板控制器（版本创建 / 发布 / 对比）。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, template_service


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


def publish_template(db: Session, template_id: int, actor_email: str, actor_role: str, request: Request) -> dict:
    result = template_service.publish_template(db, template_id, actor_email)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="template.publish",
        entity="template",
        entity_id=template_id,
        detail={"version": result["template"]["version"], "archived": result["archived"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def compare_templates(db: Session, left_id: int, right_id: int) -> dict:
    return template_service.compare_templates(db, left_id, right_id)
