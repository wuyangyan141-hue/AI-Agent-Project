import type { PetState } from '../protocol';

/** Unified desktop-pet animation states driven by WebSocket + local UX. */
export type PetAnimationState =
  | 'idle'
  | 'thinking'
  | 'searching'
  | 'tool'
  | 'talking'
  | 'success'
  | 'error';

export type ConnectionPhase = 'connecting' | 'connected' | 'disconnected';

export type ChatLine = import('../knowledge').ChatMessage;

export type BubbleCopy = Record<PetAnimationState, string>;

export const DEFAULT_BUBBLE_COPY: BubbleCopy = {
  idle: '今天想学习什么？',
  thinking: '我正在理解你的目标……',
  searching: '正在查找学习资料……',
  tool: '正在调用学习工具……',
  talking: '正在回答……',
  success: '完成啦！',
  error: '遇到了一点问题，请再试一次。',
};

export const PET_WINDOW_WIDTH = 320;
export const BUBBLE_MAX_LINES = 5;
/** Minimum time a reply stays in the pet bubble before returning to idle. */
export const SUCCESS_HOLD_MS = 8000;
export const ERROR_HOLD_MS = 5000;
/** Extra reading time for longer answers (~4 CJK chars/sec), capped. */
export const BUBBLE_READ_MS_PER_CHAR = 250;
export const BUBBLE_HOLD_MAX_MS = 28000;

/** How long to keep a finished reply visible, scaled by text length. */
export function bubbleHoldMs(text: string, kind: 'success' | 'error' = 'success'): number {
  const base = kind === 'success' ? SUCCESS_HOLD_MS : ERROR_HOLD_MS;
  const chars = text.replace(/\s+/g, '').length;
  const reading = Math.round(chars * BUBBLE_READ_MS_PER_CHAR);
  return Math.min(BUBBLE_HOLD_MAX_MS, Math.max(base, reading));
}

export function isPetAnimationState(value: string): value is PetAnimationState {
  return ['idle', 'thinking', 'searching', 'tool', 'talking', 'success', 'error'].includes(value);
}

export function asPetAnimationState(state: PetState | string): PetAnimationState {
  return isPetAnimationState(state) ? state : 'idle';
}
