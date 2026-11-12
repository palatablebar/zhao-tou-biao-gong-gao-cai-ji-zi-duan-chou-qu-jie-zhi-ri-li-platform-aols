from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class CrawlRun(Base):
    """采集批次：一次跑全部站点（或指定站点）的采集与抽取统计。"""

    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    triggered_by: Mapped[str] = mapped_column(String(160))
    site_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    field_count: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
