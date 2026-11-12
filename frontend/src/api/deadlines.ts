import { http } from './client';
import type { CalendarPayload } from '../types/models';

export const deadlineApi = {
  list: (asOf?: string, risk?: string) => {
    const search = new URLSearchParams();
    if (asOf) search.set('as_of', asOf);
    if (risk) search.set('risk', risk);
    const text = search.toString();
    return http.get<CalendarPayload>(`/deadlines${text ? `?${text}` : ''}`);
  },
  recompute: (asOf?: string) =>
    http.post<{ as_of: string; total: number; counts: Record<string, number>; formula: Record<string, string | number> }>(
      '/deadlines/recompute',
      asOf ? { as_of: asOf } : {},
    ),
};
