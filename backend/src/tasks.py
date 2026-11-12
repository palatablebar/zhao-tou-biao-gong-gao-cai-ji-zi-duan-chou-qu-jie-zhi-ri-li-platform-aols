"""Celery 任务：worker 消费（心跳 / 单站采集 / 全站巡检 / 截止风险重算）。"""
from __future__ import annotations

import time

import redis

from src.config.celery_app import HEARTBEAT_KEY, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name="bidsift.heartbeat")
def heartbeat() -> str:
    try:
        _redis().set(HEARTBEAT_KEY, time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name="bidsift.crawl_site")
def crawl_site(site_id: int) -> dict:
    """单站采集：对指定站点重跑一次采集 + 抽取（幂等，content_hash 去重）。"""
    from src.config.database import session_scope
    from src.services import crawl_service

    with session_scope() as db:
        result = crawl_service.run_crawl(db, actor_email="worker@bidsift.io", site_ids=[site_id])
        return {
            "status": "ok",
            "run_id": result["run"]["id"],
            "fetched": result["run"]["fetched_count"],
            "duplicate": result["run"]["duplicate_count"],
            "low_confidence": result["run"]["low_confidence_count"],
        }


@celery_app.task(name="bidsift.crawl_all_sites")
def crawl_all_sites() -> dict:
    from src.config.database import session_scope
    from src.services import crawl_service
    from src.utils.errors import AppError

    with session_scope() as db:
        try:
            result = crawl_service.run_crawl(db, actor_email="worker@bidsift.io")
        except AppError as exc:
            logger.warning("crawl_all_sites skipped: %s", exc.code)
            return {"status": "skipped", "reason": exc.code}
        return {
            "status": "ok",
            "run_id": result["run"]["id"],
            "fetched": result["run"]["fetched_count"],
            "fields": result["run"]["field_count"],
            "low_confidence": result["run"]["low_confidence_count"],
        }


@celery_app.task(name="bidsift.recompute_deadlines")
def recompute_deadlines() -> dict:
    from src.config.database import session_scope
    from src.services import deadline_service

    with session_scope() as db:
        result = deadline_service.recompute_events(db)
        return {"status": "ok", "as_of": result["as_of"], "counts": result["counts"]}
