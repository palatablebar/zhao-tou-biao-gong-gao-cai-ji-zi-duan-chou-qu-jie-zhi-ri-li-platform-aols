"""角色 -> 权限点映射（README 与前端 src/constants/roles.ts 同步）。"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "情报组长",
    Role.ANALYST.value: "情报专员",
    Role.CLIENT.value: "客户 BD（只读）",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "notice:read",
        "site:read",
        "site:write",
        "template:read",
        "template:write",
        "template:publish",
        "crawl:execute",
        "field:read",
        "field:review",
        "review:read",
        "deadline:read",
        "deadline:recompute",
        "export:run",
        "audit:read",
    },
    Role.ANALYST.value: {
        "notice:read",
        "site:read",
        "template:read",
        "template:write",
        "crawl:execute",
        "field:read",
        "field:review",
        "review:read",
        "deadline:read",
        "deadline:recompute",
        "export:run",
    },
    Role.CLIENT.value: {
        "notice:read",
        "site:read",
        "template:read",
        "deadline:read",
        "export:run",
    },
}

# 写接口的角色白名单（route 层 require_roles 使用）
SITE_WRITE_ROLES = (Role.ADMIN.value,)
TEMPLATE_WRITE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
TEMPLATE_PUBLISH_ROLES = (Role.ADMIN.value,)
CRAWL_EXECUTE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
FIELD_REVIEW_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
REVIEW_READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
DEADLINE_RECOMPUTE_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_READ_ROLES = (Role.ADMIN.value,)
ALL_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.CLIENT.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
