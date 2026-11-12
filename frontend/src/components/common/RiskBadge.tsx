import type { RiskLevel } from '../../types/models';
import { RISK_LABEL } from '../../constants/enums';
import { fmtNumber, fmtScore } from '../../utils/format';
import Stamp, { type StampTone } from './Stamp';

const TONE: Record<RiskLevel, StampTone> = {
  must_act: 'seal',
  watch: 'brass',
  skip: 'faint',
  unknown: 'ink',
};

interface RiskBadgeProps {
  level: RiskLevel;
  score?: number | null;
  pressure?: number | null;
  gap?: number | null;
  hours?: number | null;
  withDetail?: boolean;
}

export default function RiskBadge({ level, score, pressure, gap, hours, withDetail }: RiskBadgeProps) {
  return (
    <span className="risk-badge">
      <Stamp tone={TONE[level]} rotate={level === 'must_act' ? -3 : 1}>
        {RISK_LABEL[level]}
      </Stamp>
      {withDetail ? (
        <span className="risk-detail">
          <span>风险分 {fmtScore(score ?? null, 1)}</span>
          <span>压力 {fmtScore(pressure ?? null, 2)}</span>
          <span>资质差距 {fmtScore(gap ?? null, 2)}</span>
          <span>剩余 {fmtNumber(hours ?? null, 1)} h</span>
        </span>
      ) : null}
    </span>
  );
}
