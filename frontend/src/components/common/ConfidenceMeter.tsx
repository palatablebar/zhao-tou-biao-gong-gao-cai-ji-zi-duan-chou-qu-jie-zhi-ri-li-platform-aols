import { CONFIDENCE_FORMULA } from '../../constants/enums';
import { fmtScore } from '../../utils/format';

interface ConfidenceMeterProps {
  fieldKey?: string;
  confidence: number;
  anchorScore?: number;
  formatScore?: number;
  clarityScore?: number;
  threshold?: number;
  compact?: boolean;
}

/** 置信度三段分子条：锚点/格式/明确性，阈值线可读。 */
export default function ConfidenceMeter({
  confidence,
  anchorScore,
  formatScore,
  clarityScore,
  threshold = 0.55,
  compact = false,
}: ConfidenceMeterProps) {
  const low = confidence < threshold;
  const width = Math.max(4, Math.min(100, confidence * 100));
  const thresholdLeft = Math.min(100, Math.max(0, threshold * 100));
  return (
    <div className={`confidence ${low ? 'confidence-low' : 'confidence-ok'}${compact ? ' confidence-compact' : ''}`}>
      <div className="confidence-head">
        <span className="confidence-value">{fmtScore(confidence)}</span>
        <span className="confidence-tag">{low ? '低置信 · 进复核' : '可直接采用'}</span>
      </div>
      <div className="confidence-bar" aria-hidden="true">
        <span className="confidence-fill" style={{ width: `${width}%` }} />
        <span className="confidence-threshold" style={{ left: `${thresholdLeft}%` }} title={`阈值 ${threshold}`} />
      </div>
      {!compact ? (
        <ul className="confidence-parts">
          {CONFIDENCE_FORMULA.map((part) => {
            const value =
              part.key === 'anchor'
                ? anchorScore
                : part.key === 'format'
                  ? formatScore
                  : clarityScore;
            return (
              <li key={part.key}>
                <span className="part-label">{part.label}</span>
                <span className="part-value">{value === undefined ? '—' : fmtScore(value)}</span>
                <span className="part-weight">×{part.weight}</span>
                <span className="part-hint">{part.hint}</span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
