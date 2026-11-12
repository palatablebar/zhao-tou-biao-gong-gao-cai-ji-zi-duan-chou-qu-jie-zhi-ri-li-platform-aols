import type { ReactNode } from 'react';

interface PageHeadProps {
  kicker: string;
  title: string;
  sub?: ReactNode;
  refCode?: string;
  actions?: ReactNode;
}

export default function PageHead({ kicker, title, sub, refCode, actions }: PageHeadProps) {
  return (
    <header className="page-head">
      <div className="page-head-main">
        <div className="kicker">{kicker}</div>
        <h1>{title}</h1>
        {sub ? <div className="sub">{sub}</div> : null}
      </div>
      <div className="head-side">
        {refCode ? <div className="ref-code">卷宗编号 · {refCode}</div> : null}
        {actions ? <div className="head-actions">{actions}</div> : null}
      </div>
    </header>
  );
}
