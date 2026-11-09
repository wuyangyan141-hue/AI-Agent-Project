export type ServerEvent = { type: 'welcome' | 'reply' | 'error'; text: string };
export function parseServerEvent(raw: string): ServerEvent {
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== 'object' || !('type' in value) || !('text' in value)) throw new Error('Invalid event');
  const event = value as Record<string, unknown>;
  if (!['welcome', 'reply', 'error'].includes(String(event.type)) || typeof event.text !== 'string') throw new Error('Invalid event');
  return event as ServerEvent;
}
export function messageEvent(text: string): string { return JSON.stringify({ type: 'message', text }); }
