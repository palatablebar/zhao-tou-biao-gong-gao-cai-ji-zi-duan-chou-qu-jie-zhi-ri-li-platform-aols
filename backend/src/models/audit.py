from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import now_local


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_email: Mapped[str] = mapped_column(String(160), index=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    layer: Mapped[str] = mapped_column(String(20), default="domain")
    seed_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, index=True)
