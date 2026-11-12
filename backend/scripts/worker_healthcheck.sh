#!/bin/sh
cd /app || exit 1
python - <<'PY'
import os, sys, time
os.environ.setdefault("PYTHONPATH", "/app")
try:
    import redis
    url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    value = redis.Redis.from_url(url, decode_responses=True).get("bidsift:worker:heartbeat")
    if value and (time.time() - float(value)) < 120:
        print("worker healthy (heartbeat)")
        sys.exit(0)
except Exception:
    pass
try:
    from src.config.celery_app import celery_app
    if celery_app.control.ping(timeout=3):
        print("worker healthy (celery ping)")
        sys.exit(0)
except Exception:
    pass
print("worker unhealthy")
sys.exit(1)
PY
