"""工作日历：剔除周末与 2026 年法定节假日（简化表，见 TESTING 已知差异）。

口径：工作日 = 周一至周五且不在节假日表；工作时长 = [09:00, 18:00) 内的小时数。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from src.config.settings import settings

# 2026 年主要法定节假日（简化：不含调休上班日）
HOLIDAYS_2026: set[str] = {
    "2026-01-01",
    "2026-02-16",
    "2026-02-17",
    "2026-02-18",
    "2026-02-19",
    "2026-02-20",
    "2026-04-06",
    "2026-05-01",
    "2026-05-04",
    "2026-05-05",
    "2026-06-19",
    "2026-09-25",
    "2026-10-01",
    "2026-10-02",
    "2026-10-05",
    "2026-10-06",
    "2026-10-07",
}


def is_workday(day: date) -> bool:
    return day.weekday() < 5 and day.isoformat() not in HOLIDAYS_2026


def work_hours_between(start: datetime, end: datetime) -> float:
    """[start, end] 之间的有效工作时长（小时），跨周末/节假日自动跳过。"""
    if end <= start:
        return 0.0
    total = 0.0
    start_hour = settings.workday_start_hour
    end_hour = settings.workday_end_hour
    day = start.date()
    while day <= end.date():
        if is_workday(day):
            window_start = datetime.combine(day, time(start_hour, 0))
            window_end = datetime.combine(day, time(end_hour, 0))
            lo = max(window_start, start)
            hi = min(window_end, end)
            if hi > lo:
                total += (hi - lo).total_seconds() / 3600.0
        day += timedelta(days=1)
    return round(total, 2)


def add_workdays(start: datetime, days: int, hour: int = 17) -> datetime:
    """起算日之后第 N 个工作日（用于「报名截止后 N 个工作日」的区间估计）。"""
    cursor = datetime.combine(start.date(), time(hour, 0))
    added = 0
    while added < max(days, 1):
        cursor += timedelta(days=1)
        if is_workday(cursor.date()):
            added += 1
    return cursor
