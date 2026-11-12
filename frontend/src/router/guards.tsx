import { Navigate, useLocation } from 'react-router-dom';
import { useSyncExternalStore } from 'react';
import { authStore } from '../stores/authStore';
import { ROLE_LABEL, can } from '../constants/roles';
import type { Role } from '../types/models';

export function useAuth() {
  return useSyncExternalStore(authStore.subscribe, authStore.getState);
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const state = useAuth();
  const location = useLocation();
  if (!state.bootstrapped) {
    return <div className="main loading-panel">正在恢复档案室登录态 …</div>;
  }
  if (!state.token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequirePermission({ permission, children }: { permission: string; children: React.ReactNode }) {
  const state = useAuth();
  if (!state.user || !can(state.user.role, permission)) {
    return (
      <div className="forbidden" data-testid="forbidden">
        <div className="forbidden-card">
          <div className="forbidden-mark mono">403 · FORBIDDEN</div>
          <h1>这卷档案不在你的权限范围</h1>
          <p>
            当前角色为「{state.user ? ROLE_LABEL[state.user.role as Role] : '访客'}」，
            只能查看公告登记簿与截止日历。复核、采集与模板变更需要情报专员或情报组长权限。
          </p>
          <p className="mono forbidden-hint">后端同样会返回 403，前端隐藏按钮只是礼貌。</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
