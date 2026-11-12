import { useState } from 'react';
import type { FieldItem } from '../../types/models';
import { FIELD_STATUS_LABEL, QUAL_LABEL } from '../../constants/enums';
import { fieldApi } from '../../api/fields';
import { uiStore } from '../../stores/uiStore';
import { errorMessage } from '../../utils/errorMessage';
import { fmtDateTime } from '../../utils/format';
import ConfidenceMeter from './ConfidenceMeter';
import Stamp from './Stamp';

interface FieldReviewRowProps {
  field: FieldItem;
  canReview: boolean;
  onChanged?: () => void;
}

/** 字段核对行：公告详情页与复核队列页共用同一套「原文 → 归一值 → 置信度 → 复核动作」。 */
export default function FieldReviewRow({ field, canReview, onChanged }: FieldReviewRowProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field.value_text || '');
  const [unit, setUnit] = useState(field.unit || '万元');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const isMoney = field.field_key === 'budget_amount';
  const isDate = field.field_key === 'deadline';
  const statusTone = field.status === 'corrected' ? 'seal' : field.status === 'verified' ? 'brass' : 'ink';

  async function submitCorrection() {
    if (!value.trim()) {
      uiStore.push('warn', '修正值不能为空');
      return;
    }
    setBusy(true);
    try {
      const result = await fieldApi.correct(field.id, value.trim(), isMoney ? unit : undefined, note || undefined);
      const risk = result.deadline_event;
      uiStore.push(
        'ok',
        risk
          ? `已修正为「${result.field.value_text}」，日历风险重算为 ${risk.risk_level}（分 ${risk.risk_score}）`
          : `已修正为「${result.field.value_text}」`,
      );
      setEditing(false);
      setNote('');
      onChanged?.();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '修正失败'));
    } finally {
      setBusy(false);
    }
  }

  async function runAction(kind: 'verify' | 'reject') {
    setBusy(true);
    try {
      if (kind === 'verify') {
        await fieldApi.verify(field.id);
        uiStore.push('ok', `「${field.label}」已通过复核`);
      } else {
        await fieldApi.reject(field.id, note || undefined);
        uiStore.push('warn', `「${field.label}」已驳回`);
      }
      onChanged?.();
    } catch (error) {
      uiStore.push('error', errorMessage(error, '操作失败'));
    } finally {
      setBusy(false);
    }
  }

  const placeholder = field.value_text === null || field.value_text === undefined;

  return (
    <article className={`field-row${field.low_confidence ? ' field-row-low' : ''}`} data-field={field.field_key}>
      <header className="field-row-head">
        <span className="field-label">{field.label}</span>
        <span className="field-code mono">{field.field_key}</span>
        <Stamp tone={statusTone} rotate={-1}>
          {FIELD_STATUS_LABEL[field.status]}
        </Stamp>
        {field.low_confidence ? <Stamp tone="seal" rotate={2}>低置信</Stamp> : null}
        <span className={`field-precision mono${field.is_estimated ? ' estimated' : ''}`}>
          {field.precision === 'relative' ? '相对日期推算' : field.precision === 'partial' ? '缺年份补全' : field.precision === 'missing' ? '占位/缺失' : '绝对口径'}
        </span>
      </header>

      <dl className="field-facts">
        <div>
          <dt>原文片段</dt>
          <dd className="raw">{placeholder && !field.raw_text ? '（原文无该字段值）' : field.raw_text || '—'}</dd>
        </div>
        <div>
          <dt>归一值</dt>
          <dd className={placeholder ? 'empty' : 'value'}>
            {placeholder ? '空值 · 需人工补全' : field.value_text}
            {field.is_estimated ? <em className="estimated-flag">（推算）</em> : null}
          </dd>
        </div>
        <div>
          <dt>抽取理由</dt>
          <dd className="reason">{field.reason}</dd>
        </div>
      </dl>

      <ConfidenceMeter
        confidence={field.confidence}
        anchorScore={field.anchor_score}
        formatScore={field.format_score}
        clarityScore={field.clarity_score}
        compact={!field.low_confidence}
      />

      {canReview ? (
        <footer className="field-actions">
          {!editing ? (
            <>
              <button className="btn btn-sm" type="button" onClick={() => setEditing(true)} disabled={busy}>
                修正字段
              </button>
              <button className="btn btn-sm btn-primary" type="button" onClick={() => runAction('verify')} disabled={busy || placeholder}>
                通过复核
              </button>
              <button className="btn btn-sm btn-ghost" type="button" onClick={() => runAction('reject')} disabled={busy}>
                驳回
              </button>
              {field.reviewer ? <span className="reviewer">复核人 {field.reviewer} · {fmtDateTime(field.reviewed_at)}</span> : null}
            </>
          ) : (
            <div className="correct-form">
              <label>
                <span>{field.label}归一值</span>
                <input className="input mono" value={value} onChange={(event) => setValue(event.target.value)} />
              </label>
              {isMoney ? (
                <label>
                  <span>单位</span>
                  <select className="input" value={unit} onChange={(event) => setUnit(event.target.value)}>
                    <option value="万元">万元</option>
                    <option value="元">元</option>
                    <option value="亿元">亿元</option>
                  </select>
                </label>
              ) : null}
              <label className="grow">
                <span>{isDate ? '复核备注（可选）' : '复核备注（可选）'}</span>
                <input className="input" value={note} onChange={(event) => setNote(event.target.value)} placeholder="例如：去除「约」，按合同控制价确认" />
              </label>
              <button className="btn btn-sm btn-primary" type="button" onClick={submitCorrection} disabled={busy}>
                {busy ? '保存中…' : '保存修正'}
              </button>
              <button className="btn btn-sm btn-ghost" type="button" onClick={() => setEditing(false)} disabled={busy}>
                取消
              </button>
            </div>
          )}
        </footer>
      ) : (
        <footer className="field-actions field-actions-readonly">
          <span>只读视图 · {QUAL_LABEL.none ? '字段复核需情报专员或组长权限' : ''}</span>
        </footer>
      )}
    </article>
  );
}
