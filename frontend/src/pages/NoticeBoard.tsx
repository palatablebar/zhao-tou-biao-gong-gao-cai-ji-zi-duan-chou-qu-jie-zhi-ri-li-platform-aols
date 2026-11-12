import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { crawlApi } from '../api/crawls';
import { noticeApi } from '../api/notices';
import MetricStrip from '../components/common/MetricStrip';
import PageHead from '../components/common/PageHead';
import Stamp from '../components/common/Stamp';
import EmptyState from '../components/common/EmptyState';
import RiskBadge from '../components/common/RiskBadge';
import { useAsync } from '../hooks/useAsync';
import { useAuth } from '../router/guards';
import { can } from '../constants/roles';
import {
  CATEGORIES,
  NOTICE_STATUS_LABEL,
  REGIONS,
  RUN_STATUS_LABEL,
} from '../constants/enums';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';
import { fmtDateTime, fmtNumber, fmtScore } from '../utils/format';

export default function NoticeBoard() {
  const navigate = useNavigate();
  const auth = useAuth();
  const canCrawl = can(auth.user?.role, 'crawl:execute');
  const [query, setQuery] = useState<{ q: string; site_id?: number; region: string; category: string; confidence: string }>({
    q: '',
    region: '',
    category: '',
    confidence: '',
  });
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [running, setRunning] = useState(false);

  const meta = useAsync(() => noticeApi.boardMeta(), []);
  const list = useAsync(
    () =>
      noticeApi.list({
        q: query.q || undefined,
        site_id: query.site_id,
        region: query.region || undefined,
        category: query.category || undefined,
        confidence: query.confidence || undefined,
        page,
        page_size: 25,
      }),
    [query, page],
  );

  const overview = meta.data?.overview;
  const sites = useAsync(() => import('../api/sites').then((mod) => mod.siteApi.list()), []);
  const latestRun = overview?.latest_run;

  async function runCrawl() {
    setRunning(true);
    try {
      const result = await crawlApi.start();
      uiStore.push(
        'ok',
        `采集批次 #${result.run.id} 完成：抓取 ${result.run.fetched_count} 条，去重 ${result.run.duplicate_count} 条，` +
          `抽取 ${result.run.field_count} 字段（低置信 ${result.run.low_confidence_count}），耗时 ${result.run.duration_ms} ms`,
      );
      meta.reload();
      list.reload();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '采集批次失败'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div data-testid="notice-board">
      <PageHead
        kicker="NOTICE REGISTER · 公告登记簿"
        title="招投标公告登记簿"
        sub={
          <>
            6 个采源 · 今日批次 {latestRun ? `#${latestRun.id}（${RUN_STATUS_LABEL[latestRun.status]}）` : '尚未运行'} ·
            抽取值 <span className="mono">{overview ? overview.field_total : '—'}</span>，
            低置信 <span className="mono">{overview ? overview.field_low_confidence : '—'}</span>
          </>
        }
        refCode="BID-REG-2026"
        actions={
          canCrawl ? (
            <button className="btn btn-primary" type="button" onClick={runCrawl} disabled={running}>
              {running ? '采集中…' : '跑采集批次'}
            </button>
          ) : (
            <span className="readonly-hint mono">只读角色 · 不可运行采集</span>
          )
        }
      />

      <MetricStrip
        cells={[
          { key: 'notices', label: '公告在库', value: overview?.notice_count ?? '—', unit: '条', hint: '去重后唯一登记' },
          { key: 'fields', label: '抽取字段', value: overview?.field_total ?? '—', unit: '个', hint: '每公告 4 字段' },
          {
            key: 'low',
            label: '低置信待复核',
            value: overview?.field_low_confidence ?? '—',
            unit: '个',
            accent: true,
            hint: '置信度 < 0.55',
          },
          {
            key: 'events',
            label: '截止事件',
            value: overview?.event_count ?? '—',
            unit: '场',
            hint: `本周必投 ${overview?.risk_counts?.must_act ?? 0} 场`,
          },
          {
            key: 'budget',
            label: '在库预算合计',
            value: fmtNumber(overview?.budget_total_wan ?? 0, 0),
            unit: '万元',
            hint: '已归一为万元',
          },
        ]}
      />

      <section className="panel">
        <div className="panel-head">
          <h2>登记簿 · 全部公告</h2>
          <span className="meta mono">{list.data ? `${list.data.total} 条命中` : '加载中'}</span>
        </div>
        <div className="filter-bar">
          <form
            className="filter-inline"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
              setQuery((prev) => ({ ...prev, q: keyword.trim() }));
            }}
          >
            <input
              className="input"
              placeholder="按标题 / 登记号搜索"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <button className="btn btn-sm" type="submit">
              检索
            </button>
          </form>
          <select
            className="input"
            value={query.site_id ?? ''}
            onChange={(event) => {
              setPage(1);
              setQuery((prev) => ({ ...prev, site_id: event.target.value ? Number(event.target.value) : undefined }));
            }}
          >
            <option value="">全部采源</option>
            {(sites.data?.items ?? []).map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={query.region}
            onChange={(event) => {
              setPage(1);
              setQuery((prev) => ({ ...prev, region: event.target.value }));
            }}
          >
            <option value="">全部区域</option>
            {REGIONS.map((region) => (
              <option key={region} value={region}>
                {region}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={query.category}
            onChange={(event) => {
              setPage(1);
              setQuery((prev) => ({ ...prev, category: event.target.value }));
            }}
          >
            <option value="">全部分类</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
          <select
            className="input"
            value={query.confidence}
            onChange={(event) => {
              setPage(1);
              setQuery((prev) => ({ ...prev, confidence: event.target.value }));
            }}
          >
            <option value="">置信度不限</option>
            <option value="low">仅看含低置信字段</option>
            <option value="clean">仅看全部高置信</option>
          </select>
        </div>

        {list.loading ? (
          <div className="panel-loading">正在调阅登记簿 …</div>
        ) : list.error ? (
          <EmptyState
            title="登记簿没能打开"
            hint={errorMessage(list.error, '请检查后端服务是否就绪')}
            actionLabel="重新加载"
            onAction={list.reload}
          />
        ) : !list.data || list.data.items.length === 0 ? (
          <EmptyState
            title="没有匹配的公告"
            hint="换个关键词或把筛选条件放宽；也可以直接跑一次采集批次把六个采源的最新公告抓进来。"
            actionLabel={canCrawl ? '跑采集批次' : undefined}
            onAction={canCrawl ? runCrawl : undefined}
          />
        ) : (
          <>
            <table className="data ledger">
              <thead>
                <tr>
                  <th className="col-no">登记号</th>
                  <th>公告标题</th>
                  <th>采源</th>
                  <th>区域 / 分类</th>
                  <th className="num">预算(万元)</th>
                  <th>报名截止</th>
                  <th>抽取置信度</th>
                  <th>截止风险</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((notice) => {
                  const agg = notice.aggregate;
                  return (
                    <tr
                      key={notice.id}
                      className="clickable"
                      onClick={() => navigate(`/notices/${notice.id}`)}
                    >
                      <td className="col-no mono">{notice.external_id}</td>
                      <td className="wrap">
                        <span className="notice-title">{notice.title}</span>
                        {notice.body_kind === 'pdf' ? (
                          <Stamp tone="brass" rotate={-1}>
                            附件正文
                          </Stamp>
                        ) : null}
                        {agg.low_confidence_count > 0 ? (
                          <Stamp tone="seal" rotate={2}>
                            {agg.low_confidence_count} 低置信
                          </Stamp>
                        ) : null}
                      </td>
                      <td className="mono site-cell">{notice.site_name}</td>
                      <td>
                        {notice.region} · {notice.category}
                      </td>
                      <td className="num mono">{agg.budget_wan ? fmtNumber(agg.budget_wan, 2) : '—'}</td>
                      <td className="mono deadline-cell">
                        {agg.deadline_missing ? '待补全' : fmtDateTime(agg.deadline_text)}
                        {agg.deadline_is_estimated ? <em className="estimated-flag">推算</em> : null}
                      </td>
                      <td>
                        <span className={`conf-min mono${agg.min_confidence < list.data!.threshold ? ' low' : ''}`}>
                          {fmtScore(agg.min_confidence)}
                        </span>
                        <span className="conf-sub">最低 / {agg.field_count} 字段</span>
                      </td>
                      <td>
                        {agg.risk ? (
                          <RiskBadge level={agg.risk.risk_level} score={agg.risk.risk_score} />
                        ) : (
                          <span className="mono faint">未入日历</span>
                        )}
                      </td>
                      <td>
                        <Stamp tone={notice.status === 'tracking' ? 'seal' : 'ink'}>{NOTICE_STATUS_LABEL[notice.status]}</Stamp>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="pager">
              <button
                className="btn btn-sm btn-ghost"
                type="button"
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                disabled={page <= 1}
              >
                上一页
              </button>
              <span className="mono">
                第 {list.data.page} 页 / 共 {Math.max(1, Math.ceil(list.data.total / list.data.page_size))} 页
              </span>
              <button
                className="btn btn-sm btn-ghost"
                type="button"
                onClick={() => setPage((value) => value + 1)}
                disabled={page >= Math.ceil(list.data.total / list.data.page_size)}
              >
                下一页
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
