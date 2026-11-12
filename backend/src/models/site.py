from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class Site(Base):
    """采源站点：交易中心/招标网，含采集频率与限流配额。"""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(20), index=True)
    cadence_minutes: Mapped[int] = mapped_column(Integer, default=60)
    qps_limit: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(20), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
