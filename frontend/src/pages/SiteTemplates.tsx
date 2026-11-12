import { useEffect, useState } from 'react';
import { siteApi, templateApi } from '../api/sites';
import EmptyState from '../components/common/EmptyState';
import PageHead from '../components/common/PageHead';
import Stamp from '../components/common/Stamp';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { FIELD_STATUS_LABEL, RISK_LABEL, SITE_STATUS_LABEL, TEMPLATE_STATUS_LABEL } from '../constants/enums';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber } from '../utils/format';
import type { PublishImpact, RiskLevel, Template, TemplateCompare } from '../types/models';

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
  const [preview, setPreview] = useState<PublishImpact | null>(null);
  const [previewTarget, setPreviewTarget] = useState<Template | null>(null);
  const [publishResult, setPublishResult] = useState<PublishImpact | null>(null);
  const [ruleBase, setRuleBase] = useState<Template | null>(null);
  const [ruleAnchors, setRuleAnchors] = useState<Record<string, string>>({});

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
    setPreview(null);
    setPreviewTarget(null);
    setPublishResult(null);
    setRuleBase(null);
  }, [siteId]);

  async function loadPreview(template: Template) {
    setBusy(true);
    try {
      const result = await templateApi.previewPublish(template.id);
      setPreview(result);
      setPreviewTarget(template);
      setPublishResult(null);
    } catch (error) {
      uiStore.push('error', errorMessage(error, '发布预演失败'));
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!previewTarget) return;
    setBusy(true);
    try {
      const result = await templateApi.publish(previewTarget.id);
      setPreview(result);
      setPublishResult(result);
      uiStore.push(
        result.noop ? 'warn' : 'ok',
        result.noop
          ? `模板 v${result.template.version} 已是生效版本，未做重复重算`
          : `模板 v${result.template.version} 已生效：重算 ${result.affected_notice_count} 条公告、` +
            `保留人工值 ${result.field_summary.preserved_manual} 个字段、待补日期 ${result.deadline_summary.pending_date_count} 个`,
      );
      templates.reload();
      sites.reload();
    } catch (error) {
      setPreview(null);
      setPreviewTarget(null);
      uiStore.push('error', errorMessage(error, '发布失败'));
    } finally {
      setBusy(false);
    }
  }

  function startRuleEdit(base: Template) {
    const initial: Record<string, string> = {};
    Object.entries(base.field_rules ?? {}).forEach(([key, rule]) => {
      initial[key] = (rule.anchors ?? []).join('、');
    });
    setRuleBase(base);
    setRuleAnchors(initial);
    setPreview(null);
    setPreviewTarget(null);
    setPublishResult(null);
  }

  function parseAnchors(text: string): string[] {
    return text
      .split(/[、,，\s]+/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function createDraft(base: Template, fieldRules: Record<string, unknown>) {
    setBusy(true);
    try {
      const result = await templateApi.create({
        site_id: base.site_id,
        name: base.name,
        change_note: `由 v${base.version} 调整锚点生成的草稿`,
        coverage_score: base.coverage_score,
        field_rules: fieldRules,
      });
      uiStore.push('ok', `已创建草稿 v${result.template.version}，正在试算发布影响`);
      templates.reload();
      await loadPreview(result.template);
    } catch (error) {
      uiStore.push('error', errorMessage(error, '创建草稿失败'));
    } finally {
      setBusy(false);
    }
  }

  async function saveRuleDraft() {
    if (!ruleBase) return;
    const rules: Record<string, unknown> = {};
    Object.entries(ruleBase.field_rules ?? {}).forEach(([key, rule]) => {
      rules[key] = { anchors: parseAnchors(ruleAnchors[key] ?? ''), patterns: rule.patterns ?? [] };
    });
    await createDraft(ruleBase, rules);
    setRuleBase(null);
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
                actionLabel={canWrite && siteTemplates[0] ? '调整规则' : undefined}
                onAction={canWrite && siteTemplates[0] ? () => startRuleEdit(siteTemplates[0]) : undefined}
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
                          <button
                            className="btn btn-sm btn-primary"
                            type="button"
                            onClick={() => loadPreview(template)}
                            disabled={busy || previewTarget?.id === template.id}
                          >
                            发布生效
                          </button>
                        ) : null}
                        {canWrite ? (
                          <button className="btn btn-sm btn-ghost" type="button" onClick={() => startRuleEdit(template)} disabled={busy}>
                            调整规则
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {ruleBase ? (
            <section className="panel" data-testid="rule-editor">
              <div className="panel-head">
                <h2>调整锚点 · 基于 v{ruleBase.version}</h2>
                <span className="meta mono">用「、」分隔；保存后生成草稿并试算影响</span>
              </div>
              <div className="rule-grid">
                {Object.entries(ruleBase.field_rules ?? {}).map(([key, rule]) => (
                  <label key={key}>
                    <span>{rule.label ?? key}</span>
                    <input
                      className="input mono"
                      value={ruleAnchors[key] ?? ''}
                      onChange={(event) => setRuleAnchors({ ...ruleAnchors, [key]: event.target.value })}
                    />
                  </label>
                ))}
              </div>
              <div className="impact-actions">
                <span className="readonly-hint mono">草稿不会立即生效；试算只读，确认后才切换</span>
                <button className="btn btn-sm btn-ghost" type="button" onClick={() => setRuleBase(null)} disabled={busy}>
                  取消
                </button>
                <button className="btn btn-sm btn-primary" type="button" onClick={saveRuleDraft} disabled={busy}>
                  保存为草稿并试算
                </button>
              </div>
            </section>
          ) : null}

          {preview && previewTarget ? (
            <section className="panel publish-impact" data-testid="publish-impact">
              <div className="panel-head">
                <h2>发布影响 · v{preview.template.version}</h2>
                <span className="meta mono">
                  {publishResult ? '已切换生效' : '预演结果 · 未写入'} · 基准 {preview.as_of.slice(0, 16)}
                </span>
              </div>
              <div className="impact-scope">
                <div>
                  <span className="k">采源</span>
                  <span className="v mono">{preview.site.domain}</span>
                </div>
                <div>
                  <span className="k">上一版</span>
                  <span className="v mono">{preview.previous ? `v${preview.previous.version}` : '无'}</span>
                </div>
                <div>
                  <span className="k">历史公告</span>
                  <span className="v mono">{preview.notice_count} 条</span>
                </div>
                <div>
                  <span className="k">受影响公告</span>
                  <span className="v mono">{preview.affected_notice_count} 条</span>
                </div>
                <div>
                  <span className="k">字段变化</span>
                  <span className="v mono">{preview.field_summary.changed_value} 个</span>
                </div>
                <div>
                  <span className="k">人工保留</span>
                  <span className="v mono">{preview.field_summary.preserved_manual} 个</span>
                </div>
                <div>
                  <span className="k">待补日期</span>
                  <span className="v mono">{preview.deadline_summary.pending_date_count} 个</span>
                </div>
              </div>

              <div className="impact-grid">
                <div className="impact-block">
                  <h3>字段变化</h3>
                  {preview.field_changes.length === 0 ? (
                    <p className="panel-loading">按新规则重算后没有字段值变化。</p>
                  ) : (
                    <table className="data compact">
                      <thead>
                        <tr>
                          <th>公告</th>
                          <th>字段</th>
                          <th>原文 → 归一值</th>
                          <th className="num">置信度</th>
                          <th>状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.field_changes.map((change) => (
                          <tr key={`${change.notice_id}-${change.field_key}`}>
                            <td className="wrap small">
                              {change.title}
                              <span className="mono conf-sub">{change.external_id}</span>
                            </td>
                            <td>{change.label}</td>
                            <td className="wrap small">
                              <span className="impact-old">{change.old_value ?? '空'}</span>
                              <span className="impact-arrow mono">→</span>
                              <span className="impact-new">{change.new_value ?? '空'}</span>
                            </td>
                            <td className="num mono small">
                              {fmtNumber(change.old_confidence ?? 0, 2)} → {fmtNumber(change.new_confidence ?? 0, 2)}
                            </td>
                            <td className="small">
                              {change.status_before ? FIELD_STATUS_LABEL[change.status_before] : '新建'}
                              {change.status_before && change.status_after !== change.status_before
                                ? ` → ${FIELD_STATUS_LABEL[change.status_after ?? 'extracted']}`
                                : ''}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {preview.field_changes_truncated ? (
                    <p className="panel-foot">仅展示前 {preview.field_changes.length} 条，汇总计数不受影响。</p>
                  ) : null}
                </div>

                <div className="impact-block">
                  <h3>截止风险</h3>
                  <div className="impact-risk">
                    {(Object.keys(RISK_LABEL) as RiskLevel[]).map((level) => (
                      <div key={level} className="impact-risk-row mono">
                        <span className={`impact-risk-tag impact-risk-${level}`}>{RISK_LABEL[level]}</span>
                        <span>{preview.deadline_summary.risk_before[level] ?? 0}</span>
                        <span className="impact-arrow">→</span>
                        <span>{preview.deadline_summary.risk_after[level] ?? 0}</span>
                      </div>
                    ))}
                  </div>
                  <p className="panel-loading">
                    截止事件 {preview.deadline_summary.event_count} 个 · 重算 {preview.deadline_summary.rescored} 个 ·
                    截止时间变化 {preview.deadline_summary.event_at_changed} 个 · 档位变化 {preview.deadline_summary.risk_changed} 个
                  </p>

                  <h3>待补日期</h3>
                  {preview.pending_dates.length === 0 ? (
                    <p className="panel-loading">没有缺失截止时间的公告。</p>
                  ) : (
                    <ul className="pending-date-list">
                      {preview.pending_dates.map((item) => (
                        <li key={`${item.notice_id}-${item.kind}`}>
                          <span className="mono small">{item.external_id}</span>
                          <span className="wrap small">{item.title}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {preview.pending_dates_truncated ? (
                    <p className="panel-foot">仅展示前 {preview.pending_dates.length} 条。</p>
                  ) : null}
                </div>
              </div>

              <div className="impact-actions">
                {publishResult ? (
                  <span className="readonly-hint mono">
                    已归档旧版 {publishResult.archived?.length ?? 0} 个 · 人工修正/通过字段已原样保留
                  </span>
                ) : (
                  <span className="readonly-hint mono">
                    发布将在同一事务内重算该中心历史公告与截止风险，失败自动回滚并保留上一版
                  </span>
                )}
                <button className="btn btn-sm btn-ghost" type="button" onClick={() => { setPreview(null); setPreviewTarget(null); setPublishResult(null); }} disabled={busy}>
                  收起
                </button>
                {!publishResult ? (
                  <button className="btn btn-sm btn-primary" type="button" onClick={publish} disabled={busy}>
                    确认发布并切换
                  </button>
                ) : null}
              </div>
            </section>
          ) : null}

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
