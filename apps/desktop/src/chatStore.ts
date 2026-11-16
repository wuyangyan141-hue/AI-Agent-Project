import { useSyncExternalStore } from 'react';
import type { ChatMessage, Source } from './knowledge';
import type { HitlKind, HitlRequiredEvent, HitlSchema, ServerEvent } from './protocol';

export type PendingHitl = {
  kind: HitlKind;
  hitl: HitlSchema;
  interruptId: string;
  requestId: string;
};

export type ConversationState = {
  sessionId: string | null; messages: ChatMessage[]; scope: string; documentIds?: string[];
  pending: { id: string; updatedAt: number } | null;
  pendingHitl: PendingHitl | null;
  revision: number; origin: string; status?: {state: import('./protocol').PetState;text:string};
  openCitation?: { token: string; source: Source };
};
type Port = { postMessage(value: unknown): void; onmessage: ((event: MessageEvent) => unknown) | null; close(): void };
type Disk = { getItem(key: string): string | null; setItem(key: string, value: string): void };
const KEY = 'companion-conversation-v2';
const empty = (): ConversationState => ({ sessionId: null, messages: [], scope: 'auto', pending: null, pendingHitl: null, revision: 0, origin: '' });

export function createConversationStore(port?: Port, disk?: Disk) {
  const origin = crypto.randomUUID();
  let state = empty();
  const listeners = new Set<() => void>();
  const persist = () => { try { disk?.setItem(KEY, JSON.stringify(state)); } catch { /* storage quota */ } };
  const notify = () => listeners.forEach(listener => listener());
  try {
    const saved = JSON.parse(disk?.getItem(KEY) || 'null');
    if (saved && Array.isArray(saved.messages) && typeof saved.scope === 'string' && typeof saved.revision === 'number') {
      state = { ...empty(), ...saved, pending: null };
    }
  } catch { /* invalid local cache */ }
  function update(change: Partial<ConversationState> | ((current: ConversationState) => Partial<ConversationState>)) {
    const patch = typeof change === 'function' ? change(state) : change;
    state = { ...state, ...patch, revision: Math.max(Date.now(), state.revision + 1), origin };
    state.messages = state.messages.slice(-80);
    persist(); notify(); port?.postMessage({ kind: 'snapshot', value: state });
  }
  if (port) {
    port.onmessage = event => {
      const packet = event.data as { kind?: string; value?: ConversationState };
      if (packet.kind === 'request') { port.postMessage({ kind: 'snapshot', value: state }); return; }
      const incoming = packet.value;
      if (packet.kind !== 'snapshot' || !incoming || !Array.isArray(incoming.messages) || typeof incoming.revision !== 'number') return;
      if (incoming.revision < state.revision || (incoming.revision === state.revision && incoming.origin <= state.origin)) return;
      state = incoming; persist(); notify();
    };
    port.postMessage({ kind: 'request' });
  }
  return {
    getSnapshot: () => state,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    update,
    setMessages: (value: ChatMessage[] | ((old: ChatMessage[]) => ChatMessage[])) => update(current => ({ messages: typeof value === 'function' ? value(current.messages) : value })),
    newChat: () => update({ sessionId: null, messages: [], scope: 'auto', documentIds: [], pending: null, pendingHitl: null, status:{state:'idle',text:'今天想学习什么？'},openCitation: undefined }),
    open: (sessionId: string, messages: ChatMessage[], scope = 'auto', documentIds: string[] = []) => update({ sessionId, messages, scope, documentIds, pending: null, pendingHitl: null, openCitation: undefined }),
    cancelHitl: () => update({ pendingHitl: null, pending: null, status: { state: 'idle', text: '今天想学习什么？' } }),
    begin(text: string, scope = state.scope) {
      if (state.pending && Date.now() - state.pending.updatedAt < 90000) return null;
      const id = crypto.randomUUID();
      update(current => ({ scope, pending: { id, updatedAt: Date.now() }, status:{state:'thinking',text:'正在理解你的问题'}, messages: [...current.messages, { id: crypto.randomUUID(), role: 'user', content: text }] }));
      return id;
    },
    receiveHitl(event: HitlRequiredEvent) {
      if (!event.request_id || event.request_id !== state.pending?.id) return false;
      const interruptId = event.interrupt_id || event.session_id || state.sessionId || event.request_id;
      update((current) => {
        const refreshRevise =
          event.kind === 'plan_revise' && current.pendingHitl?.kind === 'plan_revise';
        return {
          sessionId: event.session_id || current.sessionId,
          pending: { id: event.request_id, updatedAt: Date.now() },
          pendingHitl: {
            kind: event.kind,
            hitl: event.hitl,
            interruptId,
            requestId: event.request_id,
          },
          status: { state: event.state, text: event.text },
          messages: refreshRevise
            ? current.messages
            : [
                ...current.messages,
                {
                  id: crypto.randomUUID(),
                  role: 'assistant',
                  content: event.text,
                  metadata: { mode: 'hitl' },
                },
              ],
        };
      });
      return true;
    },
    receive(event: ServerEvent) {
      if (!event.request_id || event.request_id !== state.pending?.id) return false;
      if (event.type === 'status') { update({ pending: { ...state.pending, updatedAt: Date.now() },status:{state:event.state,text:event.text} }); return true; }
      if (!['reply', 'error', 'plan_draft'].includes(event.type)) return false;
      const contextIds = event.context?.document_ids;
      update(current => ({
        sessionId: event.session_id || current.sessionId, pending: null, pendingHitl: null,status:{state:event.state,text:event.text},
        documentIds:contextIds||[],
        scope: current.scope === 'chat' ? 'chat' : contextIds?.length === 1 ? contextIds[0] : contextIds && contextIds.length > 1 ? current.scope : current.scope,
        messages: [...current.messages, { id: crypto.randomUUID(), role: 'assistant', content: event.text,
          metadata: { sources: event.sources, mode: event.answer_mode, warning: event.warning || undefined,
            draft: event.draft, kind: event.kind,
            review: event.review as import('./knowledge').ReviewPayload | undefined,
            today_plan: event.today_plan as import('./knowledge').TodayPlanPayload | undefined,
            plan_options: event.plan_options as import('./knowledge').PlanOption[] | undefined,
            offer_review: event.offer_review,
            next_step: event.next_step } }],
      }));
      return true;
    },
    expire(now = Date.now()) {
      if(state.pending && now-state.pending.updatedAt>90000)update(current=>({pending:null,status:{state:'error',text:'等待回复超时，请重试。'},messages:[...current.messages,{id:crypto.randomUUID(),role:'assistant',content:'等待回复超时，请重试。',metadata:{mode:'error'}}]}));
    },
    close: () => port?.close(),
  };
}
const channel = typeof window !== 'undefined' && typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('learning-companion-conversation-v2') : undefined;
export const conversation = createConversationStore(channel, typeof window !== 'undefined' ? window.localStorage : undefined);
if(typeof window!=='undefined')window.setInterval(()=>conversation.expire(),5000);
export function useConversation() { return useSyncExternalStore(conversation.subscribe, conversation.getSnapshot); }
export function scopeFields(scope: string, documentIds = conversation.getSnapshot().documentIds || []): { general: boolean; knowledge: boolean; document_ids?: string[] | null } {
  return { general: scope === 'chat', knowledge: !['chat','auto'].includes(scope), document_ids: scope==='selection'?documentIds:['auto','all','chat'].includes(scope) ? null : [scope] };
}
