import { useMemo, useState } from 'react';
import { PawprintButton } from './PawprintButton';
import type { HitlKind, HitlSchema } from './protocol';

type Props = {
  schema: HitlSchema;
  interruptId: string;
  kind: HitlKind;
  requestId: string;
  sessionId: string | null;
  disabled?: boolean;
  onSubmit: (payload: Record<string, string | number>, action?: string) => void;
  onCancel: () => void;
};

export function HitlPanel({ schema, kind, disabled, onSubmit, onCancel }: Props) {
  const missing = useMemo(() => new Set(schema.missing || []), [schema.missing]);
  const defaults = useMemo(() => {
    const fromSchema = schema.defaults || {};
    const fromFields: Record<string, string | number> = {};
    for (const field of schema.fields) {
      if (field.default !== undefined && fromFields[field.key] === undefined) {
        fromFields[field.key] = field.default as string | number;
      }
    }
    return { ...fromFields, ...fromSchema };
  }, [schema]);

  const [values, setValues] = useState<Record<string, string | number>>(defaults);

  function setField(key: string, raw: string) {
    const field = schema.fields.find((item) => item.key === key);
    if (field?.type === 'number') {
      const num = Number(raw);
      if (!Number.isFinite(num)) return;
      const min = field.min ?? -Infinity;
      const max = field.max ?? Infinity;
      setValues((prev) => ({ ...prev, [key]: Math.min(max, Math.max(min, num)) }));
      return;
    }
    setValues((prev) => ({ ...prev, [key]: raw }));
  }

  function buildPayload(): Record<string, string | number> {
    const payload: Record<string, string | number> = {};
    for (const field of schema.fields) {
      const value = values[field.key];
      if (value === undefined || value === '') continue;
      payload[field.key] = value;
    }
    if (schema.defaults?.draft_id !== undefined) {
      payload.draft_id = schema.defaults.draft_id as number;
    }
    if (schema.defaults?.plan_kind !== undefined) {
      payload.plan_kind = schema.defaults.plan_kind as string;
    }
    return payload;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(buildPayload(), kind === 'plan_revise' ? 'regenerate' : undefined);
  }

  const submitLabel =
    kind === 'quiz_params' ? '开始出题' : kind === 'plan_revise' ? '按修改重新生成' : '生成计划';

  return (
    <form className="hitl-panel" onSubmit={handleSubmit} aria-label={schema.title}>
      <div className="hitl-head">
        <h3>{schema.title}</h3>
        <button type="button" className="hitl-close" aria-label="关闭" onClick={onCancel}>
          ×
        </button>
      </div>
      {kind === 'plan_revise' && schema.preview ? (
        <pre className="hitl-preview" aria-label="计划预览">
          {schema.preview}
        </pre>
      ) : null}
      {schema.fields.map((field) => (
        <label
          key={field.key}
          className={`hitl-field${missing.has(field.key) ? ' hitl-field-missing' : ''}`}
        >
          <span>
            {field.label}
            {missing.has(field.key) ? '（请选择）' : ''}
          </span>
          {field.type === 'select' ? (
            <select
              aria-label={field.label}
              disabled={disabled}
              value={String(values[field.key] ?? field.default ?? '')}
              onChange={(e) => setField(field.key, e.target.value)}
            >
              {(field.options || []).map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : field.type === 'number' ? (
            <input
              type="number"
              aria-label={field.label}
              disabled={disabled}
              min={field.min}
              max={field.max}
              value={Number(values[field.key] ?? field.default ?? 0)}
              onChange={(e) => setField(field.key, e.target.value)}
            />
          ) : field.type === 'textarea' ? (
            <textarea
              aria-label={field.label}
              disabled={disabled}
              maxLength={field.maxLength ?? 800}
              placeholder={field.placeholder}
              rows={4}
              value={String(values[field.key] ?? '')}
              onChange={(e) => setField(field.key, e.target.value)}
            />
          ) : (
            <input
              type="text"
              aria-label={field.label}
              disabled={disabled}
              maxLength={field.maxLength ?? 200}
              value={String(values[field.key] ?? '')}
              onChange={(e) => setField(field.key, e.target.value)}
            />
          )}
        </label>
      ))}
      <div className="hitl-actions">
        <PawprintButton type="submit" variant="primary" disabled={disabled}>
          {submitLabel}
        </PawprintButton>
        {kind === 'plan_revise' ? (
          <PawprintButton
            type="button"
            variant="secondary"
            disabled={disabled}
            onClick={() => onSubmit(buildPayload(), 'accept')}
          >
            就用这版
          </PawprintButton>
        ) : null}
        <PawprintButton type="button" variant="quiet" onClick={onCancel}>
          取消
        </PawprintButton>
      </div>
    </form>
  );
}