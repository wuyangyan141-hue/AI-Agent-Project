export type PetState = 'idle' | 'thinking' | 'searching' | 'tool' | 'talking' | 'success' | 'error';
export type PlanDraftEvent = { id: number; steps?: { day: number; title: string; minutes: number }[]; schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[]; reason?: string };
export type CitationSource={id:string;document_id:string;chunk_id:string;filename:string;page:number|null;section:string|null;snippet:string;score:number};
export type ServerEvent = { type: 'welcome' | 'status' | 'reply' | 'error' | 'plan_draft'; text: string; state: PetState; mode?: 'demo' | 'langchain'; draft?: PlanDraftEvent; kind?: 'plan' | 'replan'; request_id?:string;context?:{document_ids:string[]|null;topic:string};review?:unknown; today_plan?:unknown; plan_options?:unknown; offer_review?:boolean; session_id?:string; sources?:CitationSource[];answer_mode?:string;warning?:string|null; next_step?: { stage: string; action: string; title: string; suggestion: string; prompt: string } };

const PET_STATES = new Set(['idle','thinking','searching','tool','talking','success','error']);

export function parseServerEvent(raw: string): ServerEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (!['welcome', 'status', 'reply', 'error', 'plan_draft'].includes(String(event.type)) || typeof event.text !== 'string' || !PET_STATES.has(String(event.state))) throw new Error('Invalid event');
  if (event.type === 'plan_draft' && (!event.draft || typeof event.draft !== 'object' || typeof (event.draft as Record<string, unknown>).id !== 'number' || ![ (event.draft as Record<string, unknown>).steps, (event.draft as Record<string, unknown>).schedule ].some(Array.isArray))) throw new Error('Invalid draft');
  if (event.type === 'plan_draft' && event.kind !== undefined && !['plan', 'replan'].includes(String(event.kind))) throw new Error('Invalid draft kind');
  if(event.sources!==undefined && (!Array.isArray(event.sources) || event.sources.some(s=>!s || typeof s!=='object' || typeof s.id!=='string' || typeof s.document_id!=='string' || typeof s.filename!=='string' || typeof s.snippet!=='string' || (s.page!==null && (!Number.isInteger(s.page)||s.page<1)))))throw new Error('Invalid sources');
  if(event.session_id!==undefined && typeof event.session_id!=='string')throw new Error('Invalid session');
  return event as ServerEvent;
}
export function messageEvent(text: string): string { return JSON.stringify({ type: 'message', text }); }
