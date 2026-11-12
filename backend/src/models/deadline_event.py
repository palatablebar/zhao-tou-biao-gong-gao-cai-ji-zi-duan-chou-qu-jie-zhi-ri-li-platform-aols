from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class DeadlineEvent(Base):
    """截止日历事件：风险评分结果落库（压力/资质差距/风险分/档位）。"""

    __tablename__ = "deadline_events"
    __table_args__ = (UniqueConstraint("notice_id", "kind", name="uq_deadline_notice_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="enroll", index=True)
    event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    precision: Mapped[str] = mapped_column(String(20), default="absolute")
    work_hours_remaining: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline_pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    qualify_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
