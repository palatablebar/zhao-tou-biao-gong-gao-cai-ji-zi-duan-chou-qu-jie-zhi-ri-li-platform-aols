from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class ExtractionTemplate(Base):
    """抽取模板版本：field_rules 里是锚点词与正则，抽取引擎按生效版本取用。"""

    __tablename__ = "extraction_templates"
    __table_args__ = (UniqueConstraint("site_id", "name", "version", name="uq_template_version"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    field_rules: Mapped[dict] = mapped_column(JSON)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    change_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
