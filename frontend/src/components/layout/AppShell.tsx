import { NavLink, useNavigate } from 'react-router-dom';
import { useSyncExternalStore } from 'react';
import { authStore } from '../../stores/authStore';
import { NAV_ITEMS, APP_KICKER, APP_STRAP } from '../../constants/ui';
import { ROLE_LABEL, can } from '../../constants/roles';
import Toasts from '../common/Toasts';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const navigate = useNavigate();
  const role = state.user?.role;
  const navItems = NAV_ITEMS.filter((item) => can(role, item.permission));

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-mark">
          <span className="rail-stamp">档案室</span>
          <strong>bid<span>sift</span></strong>
          <small>BID INTELLIGENCE ARCHIVE</small>
        </div>
        <nav className="rail-nav">
          {navItems.map((item, index) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}
            >
              <span className="rail-index mono">{String(index + 1).padStart(2, '0')}</span>
              <span className="rail-name">{item.label}</span>
              <span className="rail-hint mono">{item.hint}</span>
            </NavLink>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="rail-user">
            {state.user?.display_name ?? '未登录'}
            <small>{role ? ROLE_LABEL[role] : ''}</small>
            {state.user?.industry ? <small>行业 · {state.user.industry}</small> : null}
          </div>
          <button
            className="link-btn"
            type="button"
            onClick={() => {
              authStore.logout();
              navigate('/login');
            }}
          >
            退出登录
          </button>
        </div>
      </aside>
      <main className="main">
        <div className="strap-line">
          <span className="mono">{APP_KICKER}</span>
          <span>{APP_STRAP} · 交易日 {state.user ? '在线' : '离线'}</span>
        </div>
        <div className="main-inner">{children}</div>
      </main>
      <Toasts />
    </div>
  );
}
