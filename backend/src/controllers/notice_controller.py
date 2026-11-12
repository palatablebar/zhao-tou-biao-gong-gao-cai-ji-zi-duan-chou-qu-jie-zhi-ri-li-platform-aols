"""公告控制器。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.services import notice_service, report_service


def list_notices(db: Session, **filters) -> dict:
    result = notice_service.list_notices(db, **filters)
    return result


def get_notice(db: Session, notice_id: int) -> dict:
    return notice_service.get_notice_detail(db, notice_id)


def board_meta(db: Session) -> dict:
    return {
        "overview": report_service.overview(db),
        "status_options": notice_service.status_options(),
        "risk_options": notice_service.risk_options(),
        "industry_options": report_service.industry_options(),
    }
