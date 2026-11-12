import { ApiError } from '../api/client';

const CODE_MESSAGE: Record<string, string> = {
  AUTH_INVALID: '邮箱或密码不正确',
  AUTH_MISSING: '登录已过期，请重新登录',
  FORBIDDEN: '当前角色无权执行该操作',
  NOT_FOUND: '对象不存在或已归档',
  CONFLICT: '对象状态冲突，请刷新后重试',
  CRAWL_BUSY: '已有采集批次正在执行',
  FIELD_LOCKED: '该字段已锁定，不能再次修改',
  TEMPLATE_STATE: '模板当前状态不允许该操作',
  RATE_LIMITED: '操作过于频繁，请稍后再试',
  VALIDATION: '提交内容不合法',
  INTERNAL: '服务内部错误，请稍后重试',
};

export function errorMessage(error: unknown, fallback = '请求失败'): string {
  if (error instanceof ApiError) {
    const payload = error.payload as { code?: string; message?: string; detail?: unknown } | null;
    if (payload && payload.code && CODE_MESSAGE[payload.code]) {
      const detail = payload.detail ? `（${String(payload.detail)}）` : '';
      return `${CODE_MESSAGE[payload.code]}${detail}`;
    }
    if (error.status === 403) return CODE_MESSAGE.FORBIDDEN;
    return payload?.message || `${fallback}（HTTP ${error.status}）`;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}
