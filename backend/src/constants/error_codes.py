"""统一错误码，前端 utils/errorMessage.ts 兜底文案与之对应。"""
from __future__ import annotations

ERROR_CODES: dict[str, str] = {
    "AUTH_INVALID": "邮箱或密码不正确",
    "AUTH_MISSING": "缺少或无效的访问令牌",
    "FORBIDDEN": "当前角色无权执行该操作",
    "NOT_FOUND": "对象不存在",
    "CONFLICT": "对象状态冲突，请刷新后重试",
    "RATE_LIMITED": "请求过于频繁，请稍后再试",
    "VALIDATION": "请求参数不合法",
    "CRAWL_BUSY": "已有采集批次在执行中",
    "FIELD_LOCKED": "已复核字段不允许再次修改",
    "TEMPLATE_STATE": "模板当前状态不允许该操作",
    "INTERNAL": "服务内部错误",
}
