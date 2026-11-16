import { useMemo, useState } from 'react';
import type { HitlSchema } from './protocol';

type Props = {
  schema: HitlSchema;
  interruptId: string;
  kind: 'quiz_params' | 'plan_params';
  requestId: string;
  sessionId: string | null;
  disabled?: boolean;
  onSubmit: (payload: Record<string, string | number>) => void;
  onCancel: () => void;
};

export function HitlPanel({ schema, disabled, onSubmit, onCancel }: Props) {
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

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Record<string, string | number> = {};
    for (const field of schema.fields) {
      const value = values[field.key];
      if (value === undefined || value === '') continue;
      payload[field.key] = value;
    }
    onSubmit(payload);
  }

  const submitLabel = schema.kind === 'quiz_params' ? '开始出题' : '生成计划';

  return (
    <form className="hitl-panel" onSubmit={handleSubmit} aria-label={schema.title}>
      <h3>{schema.title}</h3>
      {schema.fields.map((field) => (
        <label key={field.key} className="hitl-field">
          <span>{field.label}</span>
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
        <button type="submit" disabled={disabled}>
          {submitLabel}
        </button>
        <button type="button" className="quiet" disabled={disabled} onClick={onCancel}>
          取消
        </button>
      </div>
    </form>
  );
}