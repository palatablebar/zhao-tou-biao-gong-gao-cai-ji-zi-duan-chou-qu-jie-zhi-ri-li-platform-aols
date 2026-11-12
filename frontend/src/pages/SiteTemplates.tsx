import { useEffect, useState } from 'react';
import { siteApi, templateApi } from '../api/sites';
import EmptyState from '../components/common/EmptyState';
import PageHead from '../components/common/PageHead';
import Stamp from '../components/common/Stamp';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { SITE_STATUS_LABEL, TEMPLATE_STATUS_LABEL } from '../constants/enums';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber } from '../utils/format';
import type { Template, TemplateCompare } from '../types/models';

export default function SiteTemplates() {
  const auth = useAuth();
  const canWrite = can(auth.user?.role, 'template:write');
  const canPublish = can(auth.user?.role, 'template:publish');
  const sites = useAsync(() => siteApi.list(), []);
  const [siteId, setSiteId] = useState<number | null>(null);
  const templates = useAsync(() => templateApi.list(siteId ?? undefined), [siteId]);
  const [leftId, setLeftId] = useState<number | null>(null);
  const [rightId, setRightId] = useState<number | null>(null);
  const [compareData, setCompareData] = useState<TemplateCompare | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (siteId === null && sites.data && sites.data.items.length > 0) {
      setSiteId(sites.data.items[0].id);
    }
  }, [sites.data, siteId]);

  const siteTemplates = (templates.data?.items ?? []).filter((item) => item.site_id === siteId);
  const activeSite = sites.data?.items.find((item) => item.id === siteId);

  useEffect(() => {
    setLeftId(null);
    setRightId(null);
    setCompareData(null);
  }, [siteId]);

  async function publish(template: Template) {
    setBusy(true);
    try {
      const result = await templateApi.publish(template.id);
      uiStore.push('ok', `模板「${result.template.name}」v${result.template.version} 已生效`);
      templates.reload();
      sites.reload();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '发布失败'));
    } finally {
      setBusy(false);
    }
  }

  async function createDraft(base: Template) {
    setBusy(true);
    try {
      const result = await templateApi.create({
        site_id: base.site_id,
        name: base.name,
        change_note: `由 v${base.version} 复制出的草稿，待补充锚点`,
        coverage_score: base.coverage_score,
        field_rules: base.field_rules,
      });
      uiStore.push('ok', `已创建草稿 v${result.template.version}`);
      templates.reload();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '创建草稿失败'));
    } finally {
      setBusy(false);
    }
  }

  async function compare() {
    if (!leftId || !rightId) {
      uiStore.push('warn', '请先选择两个版本');
      return;
    }
    setBusy(true);
    try {
      const result = await templateApi.compare(leftId, rightId);
      setCompareData(result);
    } catch (error) {
      uiStore.push('error', errorMessage(error, '版本对比失败'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="site-templates">
      <PageHead
        kicker="SOURCE & TEMPLATE · 采源与抽取模板"
        title="采源登记与模板版本"
        sub="站点结构各异，抽取规则按站点版本化管理；改一版锚点即可在不改代码的前提下修复漏抽。"
        refCode="BID-SRC-2026"
        actions={canWrite ? <span className="readonly-hint mono">可新建草稿 · 仅组长可发布</span> : <span className="readonly-hint mono">只读角色</span>}
      />

      <div className="split-narrow">
        <aside className="site-rail">
          {(sites.data?.items ?? []).map((site) => (
            <button
              key={site.id}
              type="button"
              className={`site-rail-item${site.id === siteId ? ' active' : ''}`}
              onClick={() => setSiteId(site.id)}
            >
              <strong>{site.name}</strong>
              <span className="mono">{site.domain}</span>
              <span className="site-meta">
                <span>{site.region}</span>
                <span>{site.notice_count} 条</span>
                <span>{site.cadence_minutes} min</span>
                <span className={`status-dot status-${site.status}`} title={SITE_STATUS_LABEL[site.status]} />
              </span>
              {site.low_confidence_count > 0 ? (
                <span className="site-low mono">{site.low_confidence_count} 低置信</span>
              ) : null}
            </button>
          ))}
        </aside>

        <div className="site-detail">
          {activeSite ? (
            <div className="site-summary">
              <div>
                <span className="k">采源</span>
                <span className="v mono">{activeSite.name}</span>
              </div>
              <div>
                <span className="k">状态</span>
                <span className="v">{SITE_STATUS_LABEL[activeSite.status]}</span>
              </div>
              <div>
                <span className="k">限流</span>
                <span className="v mono">{activeSite.qps_limit} QPS</span>
              </div>
              <div>
                <span className="k">公告 / 字段</span>
                <span className="v mono">
                  {activeSite.notice_count} / {activeSite.field_count}
                </span>
              </div>
              <div>
                <span className="k">低置信</span>
                <span className="v mono">{activeSite.low_confidence_count}</span>
              </div>
            </div>
          ) : null}

          <section className="panel">
            <div className="panel-head">
              <h2>模板版本</h2>
              <span className="meta mono">{siteTemplates.length} 个版本</span>
            </div>
            {templates.loading ? (
              <div className="panel-loading">正在调阅模板 …</div>
            ) : siteTemplates.length === 0 ? (
              <EmptyState
                title="该站点还没有模板"
                hint="先以默认规则创建一个草稿版本，再发布为生效版本，采集批次就会用它抽取字段。"
                actionLabel={canWrite && siteTemplates[0] ? '新建草稿' : undefined}
                onAction={canWrite && siteTemplates[0] ? () => createDraft(siteTemplates[0]) : undefined}
              />
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th>版本</th>
                    <th>模板名</th>
                    <th>状态</th>
                    <th className="num">覆盖率</th>
                    <th>变更说明</th>
                    <th>创建</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {siteTemplates.map((template) => (
                    <tr key={template.id}>
                      <td className="mono">v{template.version}</td>
                      <td>{template.name}</td>
                      <td>
                        <Stamp tone={template.status === 'active' ? 'seal' : template.status === 'draft' ? 'ink' : 'faint'}>
                          {TEMPLATE_STATUS_LABEL[template.status]}
                        </Stamp>
                      </td>
                      <td className="num mono">{fmtNumber(template.coverage_score * 100, 1)}%</td>
                      <td className="wrap">{template.change_note || '—'}</td>
                      <td className="mono small">
                        {template.created_by}
                        <br />
                        {fmtDateTime(template.created_at)}
                      </td>
                      <td className="actions-cell">
                        {canPublish && template.status === 'draft' ? (
                          <button className="btn btn-sm btn-primary" type="button" onClick={() => publish(template)} disabled={busy}>
                            发布生效
                          </button>
                        ) : null}
                        {canWrite ? (
                          <button className="btn btn-sm btn-ghost" type="button" onClick={() => createDraft(template)} disabled={busy}>
                            复制为草稿
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>版本对比</h2>
              <span className="meta mono">锚点增删 / 正则变更 / 覆盖率差</span>
            </div>
            <div className="compare-bar">
              <select className="input" value={leftId ?? ''} onChange={(event) => setLeftId(Number(event.target.value) || null)}>
                <option value="">选择左版本</option>
                {siteTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    v{template.version} · {template.name}
                  </option>
                ))}
              </select>
              <select className="input" value={rightId ?? ''} onChange={(event) => setRightId(Number(event.target.value) || null)}>
                <option value="">选择右版本</option>
                {siteTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    v{template.version} · {template.name}
                  </option>
                ))}
              </select>
              <button className="btn btn-sm" type="button" onClick={compare} disabled={busy}>
                对比
              </button>
              {compareData ? (
                <span className="mono compare-summary">
                  变更字段 {compareData.changed_field_count} 个 · 覆盖率 {compareData.coverage_delta >= 0 ? '+' : ''}
                  {fmtNumber(compareData.coverage_delta * 100, 1)}%
                </span>
              ) : null}
            </div>
            {compareData ? (
              <table className="data compare-table">
                <thead>
                  <tr>
                    <th>字段</th>
                    <th>新增锚点</th>
                    <th>删除锚点</th>
                    <th>正则变更</th>
                    <th className="num">锚点数</th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.diffs.map((diff) => (
                    <tr key={diff.field_key} className={diff.changed ? 'row-changed' : ''}>
                      <td>
                        {diff.label}
                        <span className="mono field-code-inline">{diff.field_key}</span>
                      </td>
                      <td>{diff.anchors_added.length ? diff.anchors_added.map((item) => <code key={item} className="anchor-add">+{item}</code>) : '—'}</td>
                      <td>{diff.anchors_removed.length ? diff.anchors_removed.map((item) => <code key={item} className="anchor-del">-{item}</code>) : '—'}</td>
                      <td>{diff.pattern_changed ? '有' : '无'}</td>
                      <td className="num mono">
                        {diff.left_anchor_count} → {diff.right_anchor_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="panel-loading">选择同站点的两个版本后点「对比」，会列出锚点与正则差异。</div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
