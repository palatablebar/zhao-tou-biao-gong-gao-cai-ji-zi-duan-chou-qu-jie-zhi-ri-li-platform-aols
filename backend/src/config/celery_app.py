"""Celery 入口：backend 投递任务，worker 容器消费（beat 写心跳）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

celery_app = Celery(
    "bidsift",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)

celery_app.conf.beat_schedule = {
    "bidsift-heartbeat": {"task": "bidsift.heartbeat", "schedule": 20.0},
    "bidsift-deadline-refresh": {"task": "bidsift.recompute_deadlines", "schedule": crontab(minute="*/15")},
    "bidsift-site-sweep": {"task": "bidsift.crawl_all_sites", "schedule": crontab(minute="*/30")},
}

TASK_HEARTBEAT = "bidsift.heartbeat"
TASK_CRAWL_SITE = "bidsift.crawl_site"
TASK_CRAWL_ALL = "bidsift.crawl_all_sites"
TASK_RECOMPUTE_DEADLINES = "bidsift.recompute_deadlines"
HEARTBEAT_KEY = "bidsift:worker:heartbeat"
