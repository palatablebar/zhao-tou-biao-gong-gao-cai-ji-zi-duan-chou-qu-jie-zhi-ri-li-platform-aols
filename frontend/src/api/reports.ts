import { downloadFile, http } from './client';
import type { AuditLogItem, Overview } from '../types/models';

export const reportApi = {
  overview: () => http.get<Overview>('/reports/overview'),
  weeklyCsv: (asOf?: string) =>
    downloadFile(
      `/reports/weekly-must-bid.csv${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''}`,
      'bidsift-week.csv',
    ),
  audit: (limit = 60) => http.get<{ items: AuditLogItem[] }>(`/reports/audit?limit=${limit}`),
};
