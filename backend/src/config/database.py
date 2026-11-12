"""MySQL 8.0 / SQLAlchemy 2.0 engine + session。"""
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=8,
    max_overflow=16,
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ping_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def wait_for_db(max_wait_seconds: int = 90) -> bool:
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline:
        if ping_db():
            return True
        time.sleep(2)
    return False
