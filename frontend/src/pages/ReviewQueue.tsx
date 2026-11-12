import { useState } from 'react';
import { fieldApi } from '../api/fields';
import { reportApi } from '../api/reports';
import EmptyState from '../components/common/EmptyState';
import FieldReviewRow from '../components/common/FieldReviewRow';
import MetricStrip from '../components/common/MetricStrip';
import PageHead from '../components/common/PageHead';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { FIELD_LABEL } from '../constants/enums';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber, fmtPercent } from '../utils/format';
import type { FieldKey } from '../types/models';

type Tab = 'queue' | 'gaps' | 'audit';

export default function ReviewQueue() {
  const auth = useAuth();
  const canReview = can(auth.user?.role, 'field:review');
  const canAudit = can(auth.user?.role, 'audit:read');
  const [tab, setTab] = useState<Tab>('queue');
  const queue = useAsync(() => fieldApi.reviewQueue(), []);
  const gaps = useAsync(() => fieldApi.gaps(), []);
  const audit = useAsync(() => reportApi.audit(40), []);

  const pending = queue.data?.pending_total ?? 0;
  const reviewed = queue.data?.reviewed_total ?? 0;
  const byField = queue.data?.by_field ?? {};

  return (
    <div data-testid="review-queue">
      <PageHead
        kicker="REVIEW DESK · 复核队列与漏抽报表"
        title="字段复核台"
        sub="低置信字段按分数升序排队；修正与通过都会写审计日志，并触发对应截止事件重算。"
        refCode="BID-REVIEW-2026"
        actions={
          <>
            <button className="btn btn-sm btn-ghost" type="button" onClick={() => { queue.reload(); gaps.reload(); }}>
              刷新
            </button>
            <span className="readonly-hint mono">{canReview ? '可复核' : '只读角色'}</span>
          </>
        }
      />

      <MetricStrip
        cells={[
          { key: 'pending', label: '待复核字段', value: pending, unit: '个', accent: true, hint: '置信度 < 0.55' },
          { key: 'reviewed', label: '已复核', value: reviewed, unit: '个', hint: '通过 + 修正' },
          { key: 'budget', label: '预算金额低置信', value: byField.budget_amount ?? 0, unit: '个', hint: '占位/无单位' },
          { key: 'deadline', label: '截止时间低置信', value: byField.deadline ?? 0, unit: '个', hint: '另行通知类' },
          { key: 'opening', label: '开标地点低置信', value: byField.opening_place ?? 0, unit: '个', hint: '另行通知类' },
        ]}
      />

      <div className="tab-bar">
        <button type="button" className={`tab${tab === 'queue' ? ' active' : ''}`} onClick={() => setTab('queue')}>
          复核队列 <span className="mono">{pending}</span>
        </button>
        <button type="button" className={`tab${tab === 'gaps' ? ' active' : ''}`} onClick={() => setTab('gaps')}>
          漏抽报表
        </button>
        {canAudit ? (
          <button type="button" className={`tab${tab === 'audit' ? ' active' : ''}`} onClick={() => setTab('audit')}>
            审计日志
          </button>
        ) : null}
      </div>

      {tab === 'queue' ? (
        <section className="panel">
          <div className="panel-head">
            <h2>按置信度升序排队</h2>
            <span className="meta mono">阈值 {queue.data?.threshold ?? 0.55} · 返回 {queue.data?.returned ?? 0} / {pending}</span>
          </div>
          {queue.loading ? (
            <div className="panel-loading">正在调阅复核队列 …</div>
          ) : queue.error ? (
            <EmptyState
              title="队列没能打开"
              hint={errorMessage(queue.error, '当前角色无权访问复核队列（后端返回 403）')}
              actionLabel="重新加载"
              onAction={queue.reload}
            />
          ) : (queue.data?.items.length ?? 0) === 0 ? (
            <EmptyState title="复核队列清空了" hint="所有低置信字段都已处理完；下一批采集后会重新排队。" />
          ) : (
            <div className="review-list">
              {queue.data!.items.map((field) => (
                <div key={field.id} className="review-item">
                  <div className="review-item-head">
                    <span className="mono review-notice">{field.notice?.external_id}</span>
                    <a className="review-link" href={`/notices/${field.notice_id}`}>
                      {field.notice?.title}
                    </a>
                    <span className="mono review-date">{fmtDateTime(field.notice?.published_at)}</span>
                  </div>
                  <FieldReviewRow field={field} canReview={canReview} onChanged={() => { queue.reload(); gaps.reload(); }} />
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {tab === 'gaps' ? (
        <section className="panel">
          <div className="panel-head">
            <h2>漏抽 / 缺失矩阵（站点 × 字段）</h2>
            <span className="meta mono">缺失率 = 空值字段 / 该站字段总数</span>
          </div>
          {gaps.loading ? (
            <div className="panel-loading">正在统计漏抽 …</div>
          ) : gaps.error ? (
            <EmptyState title="报表没能生成" hint={errorMessage(gaps.error)} actionLabel="重试" onAction={gaps.reload} />
          ) : (
            <>
              <table className="data gap-table">
                <thead>
                  <tr>
                    <th>采源</th>
                    {(Object.keys(FIELD_LABEL) as FieldKey[]).map((key) => (
                      <th key={key} className="num">
                        {FIELD_LABEL[key]}
                        <br />
                        缺失率 / 平均置信度
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(gaps.data?.sites ?? []).map((site) => (
                    <tr key={site.site_id}>
                      <td>
                        {site.site_name}
                        <span className="mono field-code-inline">{site.site_domain}</span>
                      </td>
                      {site.cells.map((cell) => (
                        <td key={cell.field_key} className="num">
                          <span className={`gap-rate${cell.miss_rate > 0.1 ? ' warn' : ''}`}>{fmtPercent(cell.miss_rate, 1)}</span>
                          <span className="gap-conf mono">{fmtNumber(cell.avg_confidence, 3)}</span>
                          <span className="gap-track">
                            <span className="gap-fill" style={{ width: `${Math.min(100, cell.miss_rate * 100)}%` }} />
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                  <tr className="row-total">
                    <td>全库合计</td>
                    {(gaps.data?.overall ?? []).map((cell) => (
                      <td key={cell.field_key} className="num">
                        <span className="gap-rate">{fmtPercent(cell.miss_rate, 1)}</span>
                        <span className="gap-conf mono">{fmtNumber(cell.avg_confidence, 3)}</span>
                        <span className="mono gap-count">
                          {cell.missing} / {cell.total}
                        </span>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
              <div className="panel-foot mono">
                缺失字段多为「面议 / 详见招标文件 / 另行通知」等占位话术；这类字段抽取置信度低、进复核队列，不会静默进入下游 CSV。
              </div>
            </>
          )}
        </section>
      ) : null}

      {tab === 'audit' && canAudit ? (
        <section className="panel">
          <div className="panel-head">
            <h2>审计日志</h2>
            <span className="meta mono">领域动作 + HTTP 写操作</span>
          </div>
          {audit.loading ? (
            <div className="panel-loading">正在调阅审计 …</div>
          ) : audit.error ? (
            <EmptyState title="审计日志不可用" hint={errorMessage(audit.error)} />
          ) : (
            <table className="data">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作者</th>
                  <th>动作</th>
                  <th>对象</th>
                  <th>明细</th>
                  <th>层</th>
                </tr>
              </thead>
              <tbody>
                {(audit.data?.items ?? []).map((log) => (
                  <tr key={log.id}>
                    <td className="mono small">{fmtDateTime(log.created_at)}</td>
                    <td className="mono small">
                      {log.actor_email}
                      <br />
                      <span className="faint">{log.actor_role}</span>
                    </td>
                    <td className="mono">{log.action}</td>
                    <td>
                      {log.entity}
                      {log.entity_id ? <span className="mono faint"> #{log.entity_id}</span> : null}
                    </td>
                    <td className="wrap small">{JSON.stringify(log.detail)}</td>
                    <td className="mono small">{log.layer}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}
    </div>
  );
}
