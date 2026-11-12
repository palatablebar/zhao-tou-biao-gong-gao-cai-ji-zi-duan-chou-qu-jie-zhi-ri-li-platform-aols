import { http } from './client';
import type { PublishImpact, Site, Template, TemplateCompare, TemplateDiff } from '../types/models';

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
  previewPublish: (templateId: number, asOf?: string) =>
    http.get<PublishImpact>(
      `/templates/${templateId}/publish-preview${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''}`,
    ),
  publish: (templateId: number, asOf?: string) =>
    http.post<PublishImpact>(`/templates/${templateId}/publish`, asOf ? { as_of: asOf } : {}),
  compare: (left: number, right: number) =>
    http.get<TemplateCompare & { diffs: TemplateDiff[] }>(`/templates/compare?left=${left}&right=${right}`),
};
