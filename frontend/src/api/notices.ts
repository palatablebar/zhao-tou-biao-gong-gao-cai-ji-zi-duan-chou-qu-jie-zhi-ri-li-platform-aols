import { http } from './client';
import type { NoticeDetail, NoticeList, Overview } from '../types/models';

export interface NoticeQuery {
  q?: string;
  site_id?: number;
  region?: string;
  category?: string;
  confidence?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== null) {
      search.set(key, String(value));
    }
  });
  const text = search.toString();
  return text ? `?${text}` : '';
}

export const noticeApi = {
  list: (query: NoticeQuery = {}) => http.get<NoticeList>(`/notices${toQuery(query as Record<string, string | number | undefined>)}`),
  detail: (noticeId: number) => http.get<NoticeDetail>(`/notices/${noticeId}`),
  boardMeta: () =>
    http.get<{
      overview: Overview;
      status_options: string[];
      risk_options: string[];
      industry_options: string[];
    }>('/notices/board-meta'),
};
