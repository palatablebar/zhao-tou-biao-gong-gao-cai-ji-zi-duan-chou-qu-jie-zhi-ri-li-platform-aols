"""时间工具：全库统一使用 Asia/Shanghai 本地 naive datetime（容器 TZ=Asia/Shanghai）。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

SHANGHAI = timezone(timedelta(hours=8))


def now_local() -> datetime:
    return datetime.now(SHANGHAI).replace(tzinfo=None)


def iso_local(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def parse_local(value: str | None) -> datetime | None:
    """解析前端传入的 ISO 时间；带时区的先转 Asia/Shanghai，再丢弃 tzinfo。"""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(SHANGHAI).replace(tzinfo=None)
    return parsed


def weekday_label(value: datetime) -> str:
    return "一二三四五六日"[value.weekday()]


def week_start(value: datetime) -> datetime:
    """本周一 00:00。"""
    return (value - timedelta(days=value.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def week_end(value: datetime) -> datetime:
    return week_start(value) + timedelta(days=7)
