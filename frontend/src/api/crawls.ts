import { http } from './client';
import type { CrawlResult, CrawlRun } from '../types/models';

export const crawlApi = {
  list: (limit = 20) =>
    http.get<{ items: CrawlRun[]; summary: { notice_count: number; field_count: number; run_count: number } }>(
      `/crawls?limit=${limit}`,
    ),
  start: (payload: { site_ids?: number[]; as_of?: string } = {}) =>
    http.post<CrawlResult>('/crawls', payload),
  extract: () => http.post<Record<string, number>>('/crawls/extract'),
};
