/** 角色 -> 权限点（后端 src/constants/roles.py 同源）。 */
import type { Role } from '../types/models';

export const ROLE_LABEL: Record<Role, string> = {
  admin: '情报组长',
  analyst: '情报专员',
  client: '客户 BD（只读）',
};

export const PERMISSIONS: Record<Role, string[]> = {
  admin: [
    'notice:read',
    'site:read',
    'site:write',
    'template:read',
    'template:write',
    'template:publish',
    'crawl:execute',
    'field:read',
    'field:review',
    'review:read',
    'deadline:read',
    'deadline:recompute',
    'export:run',
    'audit:read',
  ],
  analyst: [
    'notice:read',
    'site:read',
    'template:read',
    'template:write',
    'crawl:execute',
    'field:read',
    'field:review',
    'review:read',
    'deadline:read',
    'deadline:recompute',
    'export:run',
  ],
  client: ['notice:read', 'site:read', 'template:read', 'deadline:read', 'export:run'],
};

export function can(role: Role | undefined, permission: string): boolean {
  if (!role) return false;
  return PERMISSIONS[role]?.includes(permission) ?? false;
}
