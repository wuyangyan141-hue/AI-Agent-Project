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

export type ChatLine = { id: string; role: 'user' | 'assistant'; content: string };

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
export const SUCCESS_HOLD_MS = 2200;
export const ERROR_HOLD_MS = 2600;

export function isPetAnimationState(value: string): value is PetAnimationState {
  return ['idle', 'thinking', 'searching', 'tool', 'talking', 'success', 'error'].includes(value);
}

export function asPetAnimationState(state: PetState | string): PetAnimationState {
  return isPetAnimationState(state) ? state : 'idle';
}
