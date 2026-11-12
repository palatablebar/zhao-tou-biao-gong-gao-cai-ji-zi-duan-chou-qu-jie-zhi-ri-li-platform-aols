"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.site import Site  # noqa: E402
from src.models.template import ExtractionTemplate  # noqa: E402
from src.models.crawl_run import CrawlRun  # noqa: E402
from src.models.notice import Notice  # noqa: E402
from src.models.extracted_field import ExtractedField  # noqa: E402
from src.models.deadline_event import DeadlineEvent  # noqa: E402

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "Site",
    "ExtractionTemplate",
    "CrawlRun",
    "Notice",
    "ExtractedField",
    "DeadlineEvent",
]
