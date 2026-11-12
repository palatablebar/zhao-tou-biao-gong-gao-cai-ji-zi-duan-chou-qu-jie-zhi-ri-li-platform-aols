import { Link, useParams } from 'react-router-dom';
import { noticeApi } from '../api/notices';
import EmptyState from '../components/common/EmptyState';
import FieldReviewRow from '../components/common/FieldReviewRow';
import PageHead from '../components/common/PageHead';
import RiskBadge from '../components/common/RiskBadge';
import Stamp from '../components/common/Stamp';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import {
  DEADLINE_KIND_LABEL,
  FIELD_LABEL,
  NOTICE_STATUS_LABEL,
  QUAL_LABEL,
} from '../constants/enums';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber } from '../utils/format';

export default function NoticeDetail() {
  const { noticeId } = useParams();
  const auth = useAuth();
  const canReview = can(auth.user?.role, 'field:review');
  const detail = useAsync(() => noticeApi.detail(Number(noticeId)), [noticeId]);

  if (detail.loading) {
    return <div className="panel-loading">正在展开卷宗 …</div>;
  }
  if (detail.error || !detail.data) {
    return (
      <EmptyState
        title="这卷公告打不开"
        hint={errorMessage(detail.error, '可能已被归档或编号有误')}
        actionLabel="返回登记簿"
        onAction={() => {
          window.location.href = '/notices';
        }}
      />
    );
  }

  const notice = detail.data;
  const reviewed = notice.fields.filter((field) => field.status === 'verified' || field.status === 'corrected').length;

  return (
    <div data-testid="notice-detail">
      <PageHead
        kicker="NOTICE DOSSIER · 公告卷宗"
        title={notice.title}
        sub={
          <>
            <span className="mono">{notice.external_id}</span> · {notice.publisher} · {notice.region} / {notice.category} · 发布{' '}
            {fmtDateTime(notice.published_at)}
          </>
        }
        refCode={notice.external_id}
        actions={
          <Link className="btn btn-sm btn-ghost" to="/notices">
            ← 返回登记簿
          </Link>
        }
      />

      <div className="detail-meta">
        <div>
          <span className="k">采源</span>
          <span className="v mono">{notice.site.domain}</span>
        </div>
        <div>
          <span className="k">资质门槛</span>
          <span className="v">{QUAL_LABEL[notice.qualification] ?? notice.qualification}</span>
        </div>
        <div>
          <span className="k">正文形态</span>
          <span className="v mono">{notice.body_kind === 'pdf' ? 'PDF 转 HTML 附件' : 'HTML 正文'}</span>
        </div>
        <div>
          <span className="k">原文大小</span>
          <span className="v mono">{fmtNumber(notice.byte_size, 0)} B</span>
        </div>
        <div>
          <span className="k">字段复核</span>
          <span className="v mono">
            {reviewed} / {notice.fields.length}
          </span>
        </div>
        <div>
          <span className="k">状态</span>
          <span className="v">
            <Stamp tone={notice.status === 'tracking' ? 'seal' : 'ink'}>{NOTICE_STATUS_LABEL[notice.status]}</Stamp>
          </span>
        </div>
      </div>

      <div className="detail-grid">
        <section className="panel body-panel">
          <div className="panel-head">
            <h2>公告原文（清洗后）</h2>
            <span className="meta mono">锚点命中的行已用朱色标出</span>
          </div>
          <div className="body-scroll">
            {notice.body_lines.map((line, index) => (
              <p
                key={index}
                className={`body-line${line.fields.length > 0 ? ' body-line-hit' : ''}`}
              >
                <span className="line-no mono">{String(index + 1).padStart(2, '0')}</span>
                <span className="line-text">{line.text}</span>
                {line.fields.length > 0 ? (
                  <span className="line-tags">
                    {line.fields.map((field) => (
                      <span key={field} className="line-tag mono">
                        {FIELD_LABEL[field]}
                      </span>
                    ))}
                  </span>
                ) : null}
              </p>
            ))}
          </div>
          <div className="body-foot mono">
            来源 {notice.url} · 采集批次 #{notice.crawl_run_id ?? '—'} · 清洗后 {notice.body_lines.length} 行
          </div>
        </section>

        <aside className="panel field-panel">
          <div className="panel-head">
            <h2>字段核对</h2>
            <span className="meta mono">置信度 &lt; 0.55 进复核队列</span>
          </div>
          <div className="field-list">
            {notice.fields.map((field) => (
              <FieldReviewRow key={field.id} field={field} canReview={canReview} onChanged={detail.reload} />
            ))}
          </div>
        </aside>
      </div>

      <section className="panel deadline-panel">
        <div className="panel-head">
          <h2>截止日历事件</h2>
          <span className="meta mono">算法 2 · 工作日历 + 资质差距</span>
        </div>
        {notice.deadlines.length === 0 ? (
          <div className="panel-loading">该公告未进入跟踪日历（状态非「跟踪中」或日期缺失）。</div>
        ) : (
          <div className="deadline-strip">
            {notice.deadlines.map((event) => (
              <article className="deadline-card" key={event.id}>
                <header>
                  <span className="mono">{DEADLINE_KIND_LABEL[event.kind]}</span>
                  <RiskBadge level={event.risk_level} score={event.risk_score} />
                </header>
                <div className="deadline-time mono">{fmtDateTime(event.event_at)}</div>
                <div className="deadline-facts">
                  <span>剩余工作时长 {fmtNumber(event.work_hours_remaining, 1)} h</span>
                  <span>截止压力 {event.deadline_pressure ?? '—'}</span>
                  <span>资质差距 {event.qualify_gap ?? '—'}</span>
                </div>
                <p className="deadline-note">{event.note}</p>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
