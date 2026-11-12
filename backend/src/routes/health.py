from __future__ import annotations

from fastapi import APIRouter

from src.config.database import ping_db
from src.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = ping_db()
    redis_ok = False
    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        redis_ok = True
    except Exception:  # noqa: BLE001
        redis_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "service": settings.app_name,
    }
