from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class Notice(Base):
    """招标公告：保留原始 HTML 与清洗正文，content_hash 用于去重。"""

    __tablename__ = "notices"
    __table_args__ = (UniqueConstraint("site_id", "external_id", name="uq_notice_external"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    crawl_run_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_runs.id"), nullable=True, index=True)
    external_id: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(400))
    publisher: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    industry: Mapped[str] = mapped_column(String(20), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    qualification: Mapped[str] = mapped_column(String(20), default="none")
    body_kind: Mapped[str] = mapped_column(String(20), default="html")
    raw_html: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    seed_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local)
