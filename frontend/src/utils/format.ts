/** 展示层格式化：金额/百分比/时间（手动解析 ISO，避免浏览器时区把日期位移）。 */

export function fmtPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtScore(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined) return '—';
  return value.toFixed(digits);
}

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!match) return value;
  const [, year, month, day, hour, minute] = match;
  return hour ? `${year}-${month}-${day} ${hour}:${minute}` : `${year}-${month}-${day}`;
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return '—';
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : value;
}

export function fmtTime(value: string | null | undefined): string {
  if (!value) return '--:--';
  const match = value.match(/(\d{2}):(\d{2})/);
  return match ? `${match[1]}:${match[2]}` : '--:--';
}

export function weekdayOf(value: string | null | undefined): number {
  if (!value) return 0;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return 0;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return date.getUTCDay();
}

export function fmtDuration(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—';
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function shortHash(hash: string | null | undefined): string {
  return hash ? hash.slice(0, 10) : '—';
}

export function truncate(value: string | null | undefined, length = 42): string {
  if (!value) return '—';
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

export function relativeMinutes(asOf: string | null | undefined, target: string | null | undefined): string {
  if (!asOf || !target) return '—';
  const start = Date.parse(asOf);
  const end = Date.parse(target);
  if (Number.isNaN(start) || Number.isNaN(end)) return '—';
  const diff = Math.round((end - start) / 60000);
  if (diff < 0) return `已逾期 ${Math.abs(diff)} 分钟`;
  if (diff < 60) return `${diff} 分钟`;
  return `${(diff / 60).toFixed(1)} 小时`;
}
