export type PetState = 'idle' | 'thinking' | 'searching' | 'tool' | 'success' | 'error';
export type PlanDraftEvent = { id: number; steps: { day: number; title: string; minutes: number }[] };
export type ServerEvent = { type: 'welcome' | 'status' | 'reply' | 'error' | 'plan_draft'; text: string; state: PetState; mode?: 'demo' | 'langchain'; draft?: PlanDraftEvent };
export function parseServerEvent(raw: string): ServerEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (!['welcome', 'status', 'reply', 'error', 'plan_draft'].includes(String(event.type)) || typeof event.text !== 'string' || !['idle', 'thinking', 'searching', 'tool', 'success', 'error'].includes(String(event.state))) throw new Error('Invalid event');
  if (event.type === 'plan_draft' && (!event.draft || typeof event.draft !== 'object' || typeof (event.draft as Record<string, unknown>).id !== 'number' || !Array.isArray((event.draft as Record<string, unknown>).steps))) throw new Error('Invalid draft');
  return event as ServerEvent;
}
export function messageEvent(text: string): string { return JSON.stringify({ type: 'message', text }); }
