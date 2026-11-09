export type PetState = 'idle' | 'thinking' | 'searching' | 'tool' | 'success' | 'error';
export type ServerEvent = { type: 'welcome' | 'status' | 'reply' | 'error'; text: string; state: PetState; mode?: 'demo' | 'langchain' };
export function parseServerEvent(raw: string): ServerEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object') throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (!['welcome', 'status', 'reply', 'error'].includes(String(event.type)) || typeof event.text !== 'string' || !['idle', 'thinking', 'searching', 'tool', 'success', 'error'].includes(String(event.state))) throw new Error('Invalid event');
  return event as ServerEvent;
}
export function messageEvent(text: string): string { return JSON.stringify({ type: 'message', text }); }
