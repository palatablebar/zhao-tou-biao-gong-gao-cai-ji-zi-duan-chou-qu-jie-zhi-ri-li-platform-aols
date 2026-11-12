from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class ExtractedField(Base):
    """抽取字段：一行 = 一条公告的一个字段，含三段分子分与置信度。"""

    __tablename__ = "extracted_fields"
    __table_args__ = (UniqueConstraint("notice_id", "field_key", name="uq_field_notice_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    notice_id: Mapped[int] = mapped_column(ForeignKey("notices.id"), index=True)
    field_key: Mapped[str] = mapped_column(String(30), index=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_yuan: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    precision: Mapped[str] = mapped_column(String(20), default="missing")
    is_estimated: Mapped[bool] = mapped_column(default=False)
    anchor_score: Mapped[float] = mapped_column(Float, default=0.0)
    format_score: Mapped[float] = mapped_column(Float, default=0.0)
    clarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    reason: Mapped[str] = mapped_column(String(400), default="")
    status: Mapped[str] = mapped_column(String(20), default="extracted", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
