"""共享枚举（前端 src/constants/enums.ts 与 README「枚举出现位置」与之对应）。"""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    CLIENT = "client"


class SiteStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    PAUSED = "paused"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class NoticeStatus(str, Enum):
    NEW = "new"
    TRACKING = "tracking"
    REVIEWING = "reviewing"
    ARCHIVED = "archived"


class FieldKey(str, Enum):
    PROJECT_NAME = "project_name"
    BUDGET_AMOUNT = "budget_amount"
    DEADLINE = "deadline"
    OPENING_PLACE = "opening_place"


class FieldStatus(str, Enum):
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class DeadlineKind(str, Enum):
    ENROLL = "enroll"
    BID_OPEN = "bid_open"
    QA = "qa"


class RiskLevel(str, Enum):
    MUST_ACT = "must_act"
    WATCH = "watch"
    SKIP = "skip"
    UNKNOWN = "unknown"


class QualLevel(str, Enum):
    NONE = "none"
    GRADE_2 = "grade_2"
    GRADE_1 = "grade_1"
    GRADE_SPECIAL = "grade_special"


class TemplateStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


FIELD_ORDER: list[str] = [
    FieldKey.PROJECT_NAME.value,
    FieldKey.BUDGET_AMOUNT.value,
    FieldKey.DEADLINE.value,
    FieldKey.OPENING_PLACE.value,
]

# 公告分类 -> 客户行业（client 角色导出按行业过滤）
CATEGORY_INDUSTRY: dict[str, str] = {
    "市政道路": "市政",
    "桥梁隧道": "市政",
    "园林绿化": "市政",
    "房建总包": "房建",
    "装饰装修": "房建",
    "水利工程": "水利",
    "环保治理": "环保",
    "智慧城市": "交通",
}

CATEGORIES: list[str] = list(CATEGORY_INDUSTRY.keys())
INDUSTRIES: list[str] = ["市政", "房建", "水利", "环保", "交通"]

DEADLINE_KIND_LABEL: dict[str, str] = {
    DeadlineKind.ENROLL.value: "报名截止",
    DeadlineKind.BID_OPEN.value: "开标",
    DeadlineKind.QA.value: "答疑截止",
}

FIELD_LABEL: dict[str, str] = {
    FieldKey.PROJECT_NAME.value: "项目名称",
    FieldKey.BUDGET_AMOUNT.value: "预算金额",
    FieldKey.DEADLINE.value: "报名截止时间",
    FieldKey.OPENING_PLACE.value: "开标地点",
}
