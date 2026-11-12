import { http } from './client';
import type { FieldItem, GapReport, ReviewQueuePayload } from '../types/models';

export interface CorrectResult {
  field: FieldItem;
  previous_value?: string | null;
  note?: string | null;
  deadline_event: {
    id: number;
    event_at?: string | null;
    risk_level: string;
    risk_score?: number | null;
    deadline_pressure?: number | null;
  } | null;
}

export const fieldApi = {
  reviewQueue: (threshold?: number) =>
    http.get<ReviewQueuePayload>(`/review/queue${threshold ? `?threshold=${threshold}` : ''}`),
  gaps: () => http.get<GapReport>('/review/gaps'),
  correct: (fieldId: number, value: string, unit?: string, note?: string) =>
    http.patch<CorrectResult>(`/fields/${fieldId}`, { value, unit, note }),
  verify: (fieldId: number) => http.post<{ field: FieldItem }>(`/fields/${fieldId}/verify`),
  reject: (fieldId: number, note?: string) =>
    http.post<{ field: FieldItem }>(`/fields/${fieldId}/reject`, { note }),
};
