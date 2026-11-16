export type PetState = 'idle' | 'thinking' | 'searching' | 'tool' | 'talking' | 'success' | 'error';
export type PlanDraftEvent = { id: number; steps?: { day: number; title: string; minutes: number }[]; schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[]; reason?: string };
export type CitationSource={id:string;document_id:string;chunk_id:string;filename:string;page:number|null;section:string|null;snippet:string;score:number};

export type HitlField = {
  key: string;
  label: string;
  type: 'number' | 'select' | 'text' | 'textarea';
  min?: number;
  max?: number;
  maxLength?: number;
  default?: string | number;
  placeholder?: string;
  options?: { value: string; label: string }[];
};

export type HitlKind = 'quiz_params' | 'plan_params' | 'plan_revise';

export type HitlSchema = {
  kind: HitlKind;
  title: string;
  fields: HitlField[];
  defaults?: Record<string, string | number>;
  preview?: string;
  missing?: string[];
};

export type ServerEvent = {
  type: 'welcome' | 'status' | 'reply' | 'error' | 'plan_draft';
  text: string;
  state: PetState;
  mode?: 'demo' | 'langchain';
  draft?: PlanDraftEvent;
  kind?: 'plan' | 'replan';
  request_id?: string;
  context?: { document_ids: string[] | null; topic: string };
  review?: unknown;
  today_plan?: unknown;
  plan_options?: unknown;
  offer_review?: boolean;
  session_id?: string;
  sources?: CitationSource[];
  answer_mode?: string;
  warning?: string | null;
  next_step?: { stage: string; action: string; title: string; suggestion: string; prompt: string };
};

export type HitlRequiredEvent = {
  type: 'hitl_required';
  text: string;
  state: PetState;
  request_id: string;
  session_id?: string;
  kind: HitlKind;
  interrupt_id?: string;
  hitl: HitlSchema;
};

const PET_STATES = new Set(['idle','thinking','searching','tool','talking','success','error']);
const HITL_KINDS = new Set(['quiz_params', 'plan_params', 'plan_revise']);

function assertHitlSchema(value: unknown): HitlSchema {
  if (!value || typeof value !== 'object') throw new Error('Invalid hitl');
  const hitl = value as Record<string, unknown>;
  if (!HITL_KINDS.has(String(hitl.kind))) throw new Error('Invalid hitl kind');
  if (typeof hitl.title !== 'string') throw new Error('Invalid hitl');
  if (!Array.isArray(hitl.fields)) throw new Error('Invalid hitl fields');
  return value as HitlSchema;
}

export function parseHitlRequired(raw: string): HitlRequiredEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (event.type !== 'hitl_required') throw new Error('Invalid event');
  if (typeof event.text !== 'string' || !PET_STATES.has(String(event.state))) throw new Error('Invalid event');
  if (typeof event.request_id !== 'string') throw new Error('Invalid event');
  if (!HITL_KINDS.has(String(event.kind))) throw new Error('Invalid hitl kind');
  const hitl = assertHitlSchema(event.hitl);
  return {
    type: 'hitl_required',
    text: event.text,
    state: event.state as PetState,
    request_id: event.request_id,
    session_id: typeof event.session_id === 'string' ? event.session_id : undefined,
    kind: event.kind as HitlKind,
    interrupt_id: typeof event.interrupt_id === 'string' ? event.interrupt_id : undefined,
    hitl,
  };
}

export function parseServerEvent(raw: string): ServerEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (event.type === 'hitl_required') throw new Error('Invalid event');
  if (!['welcome', 'status', 'reply', 'error', 'plan_draft'].includes(String(event.type)) || typeof event.text !== 'string' || !PET_STATES.has(String(event.state))) throw new Error('Invalid event');
  if (event.type === 'plan_draft' && (!event.draft || typeof event.draft !== 'object' || typeof (event.draft as Record<string, unknown>).id !== 'number' || ![ (event.draft as Record<string, unknown>).steps, (event.draft as Record<string, unknown>).schedule ].some(Array.isArray))) throw new Error('Invalid draft');
  if (event.type === 'plan_draft' && event.kind !== undefined && !['plan', 'replan'].includes(String(event.kind))) throw new Error('Invalid draft kind');
  if (
    event.sources !== undefined &&
    (!Array.isArray(event.sources) ||
      event.sources.some(
        (s) =>
          !s ||
          typeof s !== 'object' ||
          typeof s.id !== 'string' ||
          typeof s.document_id !== 'string' ||
          typeof s.filename !== 'string' ||
          typeof s.snippet !== 'string' ||
          (s.page !== null && (!Number.isInteger(s.page) || s.page < 1)),
      ))
  ) {
    throw new Error('Invalid sources');
  }
  if (event.session_id !== undefined && typeof event.session_id !== 'string') throw new Error('Invalid session');
  return event as ServerEvent;
}

export function messageEvent(text: string): string {
  return JSON.stringify({ type: 'message', text });
}