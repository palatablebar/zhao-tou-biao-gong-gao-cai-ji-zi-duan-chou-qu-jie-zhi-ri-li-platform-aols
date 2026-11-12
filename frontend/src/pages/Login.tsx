import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { authStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const DEMO_ACCOUNTS = [
  { email: 'admin@bidsift.io', label: '情报组长 · 周敏', note: '采源/模板/复核/导出全权' },
  { email: 'analyst@bidsift.io', label: '情报专员 · 陈拓', note: '跑采集、复核字段、改模板草稿' },
  { email: 'client@bidsift.io', label: '客户 BD · 林岚', note: '只读公告与日历，仅导出本行业名单' },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@bidsift.io');
  const [password, setPassword] = useState('Demo@2026');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await authApi.login(email.trim(), password);
      authStore.setSession(result.access_token, result.user);
      navigate('/notices', { replace: true });
    } catch (err) {
      setError(errorMessage(err, '登录失败'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-brand">
        <div className="login-cover">
          <div className="cover-stamp mono">招标情报 · 档案室</div>
          <h1 className="cover-title">
            bid<span>sift</span>
          </h1>
          <p className="cover-sub">招投标公告采集 · 字段抽取 · 截止日历</p>
          <p className="cover-quote">
            六个交易中心的公告每天滚进来，
            <br />
            我们要在 <em>截止之前</em> 把该投的卷宗挑出来。
          </p>
          <ul className="cover-stats">
            <li>
              <strong className="mono">06</strong>
              <span>采源站点</span>
            </li>
            <li>
              <strong className="mono">120</strong>
              <span>公告在库</span>
            </li>
            <li>
              <strong className="mono">480</strong>
              <span>抽取字段</span>
            </li>
            <li>
              <strong className="mono">18</strong>
              <span>截止事件</span>
            </li>
          </ul>
          <div className="cover-foot mono">中鼎工程咨询有限公司 · 投标情报组 · 12 人 · 服务 5 家建筑工程客户</div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <div className="login-kicker mono">ARCHIVE ACCESS · 卷宗借阅登记</div>
          <h2>登记后才可翻阅</h2>
          <p className="sub">用演示账号登录；不同角色能看到的卷宗与可执行的动作不同，后端会真实校验。</p>
          <form onSubmit={submit}>
            <label className="field">
              <span>邮箱</span>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>密码</span>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error ? <div className="form-error">{error}</div> : null}
            <button className="btn btn-primary btn-block" type="submit" disabled={busy}>
              {busy ? '正在调阅档案…' : '进入档案室'}
            </button>
          </form>

          <div className="hint-accounts">
            <div className="hint-title mono">演示账号（密码统一 Demo@2026）</div>
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                className={`account-chip${email === account.email ? ' active' : ''}`}
                onClick={() => {
                  setEmail(account.email);
                  setPassword('Demo@2026');
                }}
              >
                <span className="mono">{account.email}</span>
                <span className="account-label">{account.label}</span>
                <span className="account-note">{account.note}</span>
              </button>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
