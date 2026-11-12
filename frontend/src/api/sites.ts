import { http } from './client';
import type { Site, Template, TemplateCompare, TemplateDiff } from '../types/models';

export const siteApi = {
  list: () => http.get<{ items: Site[] }>('/sites'),
  update: (siteId: number, payload: Record<string, unknown>) =>
    http.patch<{ site: Site; changed: Record<string, unknown> }>(`/sites/${siteId}`, payload),
};

export const templateApi = {
  list: (siteId?: number) =>
    http.get<{ items: Template[]; default_rules: Record<string, unknown> }>(
      siteId ? `/templates?site_id=${siteId}` : '/templates',
    ),
  create: (payload: Record<string, unknown>) =>
    http.post<{ template: Template }>('/templates', payload),
  publish: (templateId: number) =>
    http.post<{ template: Template; archived: number[] }>(`/templates/${templateId}/publish`),
  compare: (left: number, right: number) =>
    http.get<TemplateCompare & { diffs: TemplateDiff[] }>(`/templates/compare?left=${left}&right=${right}`),
};
