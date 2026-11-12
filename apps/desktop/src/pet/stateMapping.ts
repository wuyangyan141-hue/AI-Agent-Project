import type { ServerEvent } from '../protocol';
import { DEFAULT_BUBBLE_COPY, asPetAnimationState, type PetAnimationState } from './types';

export type MappedPetUpdate = {
  animation: PetAnimationState;
  bubbleText: string;
  assistantMessage?: string;
  sessionId?: string;
  finished: boolean;
};

/** Map a server WebSocket event into pet animation + bubble copy. */
export function mapServerEventToPet(event: ServerEvent, sending: boolean): MappedPetUpdate {
  const animation = asPetAnimationState(event.state);
  if (event.type === 'status') {
    const bubbleText =
      animation === 'idle' && sending
        ? DEFAULT_BUBBLE_COPY.talking
        : DEFAULT_BUBBLE_COPY[animation] || event.text;
    return {
      animation: sending && animation === 'idle' ? 'talking' : animation,
      bubbleText,
      sessionId: event.session_id,
      finished: false,
    };
  }
  if (event.type === 'reply' || event.type === 'plan_draft') {
    return {
      animation: 'success',
      bubbleText: event.text.trim() || DEFAULT_BUBBLE_COPY.success,
      assistantMessage: event.text,
      sessionId: event.session_id,
      finished: true,
    };
  }
  if (event.type === 'error') {
    return {
      animation: 'error',
      bubbleText: event.text.trim() || DEFAULT_BUBBLE_COPY.error,
      assistantMessage: event.text,
      sessionId: event.session_id,
      finished: true,
    };
  }
  return {
    animation: 'idle',
    bubbleText: DEFAULT_BUBBLE_COPY.idle,
    sessionId: event.session_id,
    finished: false,
  };
}

export function canSendMessage(connection: 'connecting' | 'connected' | 'disconnected', text: string, sending: boolean): boolean {
  return connection === 'connected' && text.trim().length > 0 && !sending;
}

export function nextIdleAfterTerminal(animation: PetAnimationState): PetAnimationState | null {
  if (animation === 'success' || animation === 'error') return 'idle';
  return null;
}
