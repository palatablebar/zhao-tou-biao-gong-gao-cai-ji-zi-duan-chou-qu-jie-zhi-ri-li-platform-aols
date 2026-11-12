import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import DeadlineCalendar from '../pages/DeadlineCalendar';
import Login from '../pages/Login';
import NoticeBoard from '../pages/NoticeBoard';
import NoticeDetail from '../pages/NoticeDetail';
import ReviewQueue from '../pages/ReviewQueue';
import SiteTemplates from '../pages/SiteTemplates';
import { RequireAuth, RequirePermission } from './guards';

function Protected({ permission, children }: { permission: string; children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>
        <RequirePermission permission={permission}>{children}</RequirePermission>
      </AppShell>
    </RequireAuth>
  );
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/notices" replace />} />
      <Route path="/notices" element={<Protected permission="notice:read"><NoticeBoard /></Protected>} />
      <Route path="/notices/:noticeId" element={<Protected permission="notice:read"><NoticeDetail /></Protected>} />
      <Route path="/calendar" element={<Protected permission="deadline:read"><DeadlineCalendar /></Protected>} />
      <Route path="/sites" element={<Protected permission="site:read"><SiteTemplates /></Protected>} />
      <Route path="/review" element={<Protected permission="review:read"><ReviewQueue /></Protected>} />
      <Route path="*" element={<Navigate to="/notices" replace />} />
    </Routes>
  );
}
