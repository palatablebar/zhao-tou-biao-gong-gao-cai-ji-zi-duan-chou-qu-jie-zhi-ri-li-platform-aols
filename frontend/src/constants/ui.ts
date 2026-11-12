export interface NavItem {
  to: string;
  label: string;
  hint: string;
  permission: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/notices', label: '公告登记簿', hint: 'NOTICE', permission: 'notice:read' },
  { to: '/calendar', label: '截止日历', hint: 'DEADLINE', permission: 'deadline:read' },
  { to: '/sites', label: '采源与模板', hint: 'SOURCE', permission: 'site:read' },
  { to: '/review', label: '复核队列', hint: 'REVIEW', permission: 'review:read' },
];

export const APP_STRAP = '中鼎工程咨询 · 投标情报组';
export const APP_KICKER = 'BID INTELLIGENCE ARCHIVE · 2026';
