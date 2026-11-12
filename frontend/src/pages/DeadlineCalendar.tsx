import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deadlineApi } from '../api/deadlines';
import { reportApi } from '../api/reports';
import EmptyState from '../components/common/EmptyState';
import PageHead from '../components/common/PageHead';
import RiskBadge from '../components/common/RiskBadge';
import Stamp from '../components/common/Stamp';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import { DEADLINE_KIND_LABEL, RISK_LABEL } from '../constants/enums';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber, fmtTime, weekdayOf } from '../utils/format';
import type { CalendarEvent, RiskLevel } from '../types/models';

const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function addDays(iso: string, days: number): string {
  const parts = iso.slice(0, 10).split('-').map(Number);
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + days));
  return date.toISOString().slice(0, 10);
}

function mondayOf(iso: string): string {
  const parts = iso.slice(0, 10).split('-').map(Number);
  const date = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
  const weekday = date.getUTCDay();
  const offset = weekday === 0 ? -6 : 1 - weekday;
  return addDays(iso, offset);
}

export default function DeadlineCalendar() {
  const navigate = useNavigate();
  const auth = useAuth();
  const canRecompute = can(auth.user?.role, 'deadline:recompute');
  const calendar = useAsync(() => deadlineApi.list(), []);
  const [busy, setBusy] = useState(false);

  const asOf = calendar.data?.as_of ?? '2026-11-12T09:00:00';
  const weekStart = useMemo(() => mondayOf(asOf), [asOf]);
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart],
  );
  const events = calendar.data?.items ?? [];
  const byDay = useMemo(() => {
    const grouped: Record<string, CalendarEvent[]> = {};
    events.forEach((event) => {
      if (!event.event_at) return;
      const day = event.event_at.slice(0, 10);
      grouped[day] = grouped[day] ?? [];
      grouped[day].push(event);
    });
    Object.values(grouped).forEach((list) =>
      list.sort((a, b) => (a.event_at ?? '').localeCompare(b.event_at ?? '')),
    );
    return grouped;
  }, [events]);

  const weekMustBid = events.filter(
    (event) => event.risk_level === 'must_act' && event.event_at && event.event_at.slice(0, 10) >= weekStart && event.event_at.slice(0, 10) < addDays(weekStart, 7),
  );

  const riskCounts: Record<RiskLevel, number> = { must_act: 0, watch: 0, skip: 0, unknown: 0 };
  events.forEach((event) => {
    riskCounts[event.risk_level] = (riskCounts[event.risk_level] ?? 0) + 1;
  });
  const total = events.length || 1;

  async function recompute() {
    setBusy(true);
    try {
      const result = await deadlineApi.recompute(asOf);
      uiStore.push(
        'ok',
        `风险已按基准时刻 ${result.as_of.slice(0, 16)} 重算：必投 ${result.counts.must_act ?? 0} / 观察 ${result.counts.watch ?? 0} / 放弃 ${result.counts.skip ?? 0} / 待补 ${result.counts.unknown ?? 0}`,
      );
      calendar.reload();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '重算失败'));
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    setBusy(true);
    try {
      const filename = await reportApi.weeklyCsv(asOf);
      uiStore.push('ok', `已导出 ${filename}（本周必投 ${weekMustBid.length} 行）`);
    } catch (error) {
      uiStore.push('error', errorMessage(error, '导出失败（客户角色只能导出本行业）'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div data-testid="deadline-calendar">
      <PageHead
        kicker="DEADLINE LEDGER · 截止日历"
        title="本周截止排期"
        sub={
          <>
            基准时刻 <span className="mono">{asOf.slice(0, 16)}</span> · 共 {events.length} 个截止事件 · 本周必投{' '}
            <strong>{weekMustBid.length}</strong> 场
          </>
        }
        refCode="BID-DEADLINE-2026"
        actions={
          <>
            {canRecompute ? (
              <button className="btn btn-sm" type="button" onClick={recompute} disabled={busy}>
                重算风险
              </button>
            ) : null}
            <button className="btn btn-primary btn-sm" type="button" onClick={exportCsv} disabled={busy}>
              导出本周必投 CSV
            </button>
          </>
        }
      />

      {calendar.loading ? (
        <div className="panel-loading">正在展开日历 …</div>
      ) : calendar.error ? (
        <EmptyState
          title="日历没能打开"
          hint={errorMessage(calendar.error, '请确认后端与数据库就绪')}
          actionLabel="重新加载"
          onAction={calendar.reload}
        />
      ) : (
        <div className="calendar-layout">
          <section className="week-board">
            {days.map((day, index) => {
              const dayEvents = byDay[day] ?? [];
              const isToday = day === asOf.slice(0, 10);
              return (
                <div key={day} className={`week-col${isToday ? ' week-col-today' : ''}`}>
                  <header className="week-head">
                    <span className="week-label">{WEEK_LABELS[index]}</span>
                    <span className="week-date mono">{day.slice(5)}</span>
                    <span className="week-count mono">{dayEvents.length}</span>
                  </header>
                  <div className="week-body">
                    {dayEvents.length === 0 ? (
                      <div className="week-empty mono">—</div>
                    ) : (
                      dayEvents.map((event) => (
                        <button
                          key={event.id}
                          type="button"
                          className={`event-card event-${event.risk_level}`}
                          onClick={() => navigate(`/notices/${event.notice_id}`)}
                        >
                          <span className="event-time mono">{fmtTime(event.event_at)}</span>
                          <span className="event-kind mono">{DEADLINE_KIND_LABEL[event.kind]}</span>
                          <span className="event-title">{event.notice.title}</span>
                          <span className="event-meta mono">
                            {event.notice.region} · 压力 {fmtNumber(event.deadline_pressure, 2)}
                          </span>
                          <RiskBadge level={event.risk_level} score={event.risk_score} />
                        </button>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </section>

          <aside className="calendar-side">
            <section className="panel">
              <div className="panel-head">
                <h2>本周必投名单</h2>
                <span className="meta mono">{weekMustBid.length} 行</span>
              </div>
              <ol className="must-bid-list">
                {weekMustBid.map((event, index) => (
                  <li key={event.id}>
                    <span className="index mono">{String(index + 1).padStart(2, '0')}</span>
                    <div>
                      <div className="must-bid-title">{event.notice.title}</div>
                      <div className="must-bid-meta mono">
                        {fmtDateTime(event.event_at)} · {event.notice.region}
                      </div>
                    </div>
                    <Stamp tone="seal" rotate={-2}>
                      必投
                    </Stamp>
                  </li>
                ))}
              </ol>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>风险分布</h2>
                <span className="meta mono">算法 2 · 三档 + 待补</span>
              </div>
              <div className="risk-distribution">
                {(Object.keys(riskCounts) as RiskLevel[]).map((level) => (
                  <div className={`risk-bar-row risk-row-${level}`} key={level}>
                    <span className="risk-bar-label">{RISK_LABEL[level]}</span>
                    <div className="risk-bar-track">
                      <span className="risk-bar-fill" style={{ width: `${(riskCounts[level] / total) * 100}%` }} />
                    </div>
                    <span className="risk-bar-value mono">{riskCounts[level]}</span>
                  </div>
                ))}
              </div>
              <ul className="formula-list">
                {Object.entries(calendar.data?.formula ?? {}).map(([key, value]) => (
                  <li key={key}>
                    <code className="mono">{key}</code>
                    <span>{String(value)}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>全部截止事件</h2>
                <span className="meta mono">{events.length} 条</span>
              </div>
              <table className="data compact">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>公告</th>
                    <th className="num">风险分</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.id} className="clickable" onClick={() => navigate(`/notices/${event.notice_id}`)}>
                      <td className="mono small">{fmtDateTime(event.event_at)}</td>
                      <td className="wrap small">{event.notice.title}</td>
                      <td className="num mono">{event.risk_score ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
