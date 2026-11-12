import type { ReactNode } from 'react';

export interface MetricCell {
  key: string;
  label: string;
  value: ReactNode;
  unit?: string;
  accent?: boolean;
  hint?: string;
}

export default function MetricStrip({ cells }: { cells: MetricCell[] }) {
  return (
    <div className="metrics">
      {cells.map((cell) => (
        <div className={`metric${cell.accent ? ' metric-accent' : ''}`} key={cell.key}>
          <div className="k">{cell.label}</div>
          <div className="v">
            {cell.value}
            {cell.unit ? <small>{cell.unit}</small> : null}
          </div>
          {cell.hint ? <div className="metric-hint">{cell.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}
