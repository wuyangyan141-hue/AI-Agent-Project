import type { PetAnimationState } from './types';
import dogAtlas from '../assets/dog-atlas.webp';
import basePuppy from '../assets/puppy.png';

/**
 * Animation asset contract for the desktop pet.
 *
 * Active mode uses the transparent 4×5 `dog-atlas.webp` from the shared GitHub
 * project. Extra local clips (wave / sleep / peek) reuse the same atlas cells.
 */
export type AnimationMode = 'temporary-layers' | 'sprite-atlas';
export type PetLookDirection = 'left' | 'right' | 'up' | 'down';
export type PetClip =
  | PetAnimationState
  | 'wave'
  | 'sleep'
  | 'peek'
  | 'stretch'
  | 'drag'
  | 'dragLeft'
  | 'dragRight'
  | 'dragUp'
  | 'dragDown';

/** Idle-only flavour clips that play between normal idle loops. */
/** stretch first — look-up is the most obvious standby motion. */
export const IDLE_FLAVOUR_CLIPS = ['stretch', 'peek', 'sleep'] as const;
export type IdleFlavourClip = (typeof IDLE_FLAVOUR_CLIPS)[number];

export function isIdleFlavour(clip: PetClip): clip is IdleFlavourClip {
  return (IDLE_FLAVOUR_CLIPS as readonly string[]).includes(clip);
}

export type PetFrameSet = {
  /** Ordered atlas cell indices (row-major, 4 columns). */
  frames: number[];
  /** Frame duration in ms. */
  frameMs: number;
  /** Whether playback loops until the state changes. */
  loop: boolean;
};

export const ANIMATION_MODE: AnimationMode = 'sprite-atlas';
export const ATLAS_COLUMNS = 4;
export const ATLAS_ROWS = 5;
export const PET_ATLAS = dogAtlas;
export const PET_BASE_SPRITE = basePuppy;

/**
 * Atlas cell map (4×5):
 * 0-3 blink/wag · 4-7 look up · 8-11 look around · 12-15 talk · 16-19 wave
 */
export const PET_FRAME_SETS: Record<PetClip, PetFrameSet> = {
  // Fast blink while idle (1/2 ≈ closed); hold open eyes a bit longer between blinks.
  idle: { frames: [0, 0, 1, 2, 1, 0, 0, 0, 3, 0, 0, 1, 2, 1, 0], frameMs: 180, loop: true },
  thinking: { frames: [4, 5, 6, 7, 6, 5], frameMs: 260, loop: true },
  searching: { frames: [8, 9, 10, 11, 10, 9], frameMs: 220, loop: true },
  tool: { frames: [4, 5, 12, 13, 5, 4], frameMs: 240, loop: true },
  talking: { frames: [12, 13, 14, 15, 14, 13], frameMs: 180, loop: true },
  success: { frames: [16, 17, 18, 19, 18, 17], frameMs: 200, loop: false },
  error: { frames: [1, 2, 1, 7, 1, 2], frameMs: 360, loop: true },
  // Local flavour clips composed from the same sheet
  wave: { frames: [16, 17, 18, 19, 18, 17, 16], frameMs: 180, loop: false },
  sleep: { frames: [1, 2, 2, 2, 2, 2, 1, 0], frameMs: 420, loop: false },
  peek: { frames: [8, 9, 10, 11, 10, 9, 8, 0], frameMs: 200, loop: false },
  // Extra idle: look up / stretch — clearly different from blink
  stretch: { frames: [4, 5, 6, 7, 7, 6, 5, 4, 0], frameMs: 200, loop: false },
  // Dragging: one-way look only. Horizontal right = left frames + CSS scaleX(-1).
  // Do NOT include look-around frames that glance the opposite way (e.g. 10/11).
  drag: { frames: [9, 8, 9, 8], frameMs: 320, loop: true },
  dragLeft: { frames: [9, 8, 9, 8], frameMs: 300, loop: true },
  dragRight: { frames: [9, 8, 9, 8], frameMs: 300, loop: true },
  dragUp: { frames: [4, 5, 6, 7, 6, 5], frameMs: 300, loop: true },
  dragDown: { frames: [1, 2, 1, 2], frameMs: 300, loop: true },
};

export function dragClipFor(direction: PetLookDirection | null | undefined): PetClip {
  if (direction === 'left') return 'dragLeft';
  if (direction === 'right') return 'dragRight';
  if (direction === 'up') return 'dragUp';
  if (direction === 'down') return 'dragDown';
  return 'drag';
}

export function lookFromDelta(dx: number, dy: number, min = 2): PetLookDirection | null {
  if (Math.abs(dx) < min && Math.abs(dy) < min) return null;
  if (Math.abs(dx) >= Math.abs(dy)) return dx < 0 ? 'left' : 'right';
  return dy < 0 ? 'up' : 'down';
}

export function usesSpriteAtlas(): boolean {
  return ANIMATION_MODE === 'sprite-atlas';
}

export function atlasBackgroundPosition(frame: number): string {
  const col = frame % ATLAS_COLUMNS;
  const row = Math.floor(frame / ATLAS_COLUMNS);
  const x = (col * 100) / (ATLAS_COLUMNS - 1);
  const y = (row * 100) / (ATLAS_ROWS - 1);
  return `${x}% ${y}%`;
}

export function preloadPetArt(): Promise<void> {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve();
    image.onerror = () => resolve();
    image.src = PET_ATLAS;
  });
}
