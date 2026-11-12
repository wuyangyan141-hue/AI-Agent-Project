import React, { useEffect, useRef, useState } from 'react';
import {
  IDLE_FLAVOUR_CLIPS,
  PET_ATLAS,
  PET_FRAME_SETS,
  atlasBackgroundPosition,
  dragClipFor,
  isIdleFlavour,
  lookFromDelta,
  preloadPetArt,
  usesSpriteAtlas,
  type PetClip,
  type PetLookDirection,
} from './animationAssets';
import type { PetAnimationState } from './types';

const DRAG_THRESHOLD = 7;
/** First idle flavour appears quickly so standby motion is obvious. */
const IDLE_FLAVOUR_FIRST_MS = 1500;
const IDLE_FLAVOUR_MIN_MS = 3200;
const IDLE_FLAVOUR_JITTER_MS = 1800;

/**
 * Desktop pet character driven by the shared transparent dog atlas (4×5).
 * Body can be dragged (direction-aware look); click plays wave then callback.
 */
export function PetCharacter({
  state,
  dragging = false,
  lookDirection = null,
  className = '',
  onClick,
  onDoubleClick,
  onBodyDrag,
}: {
  state: PetAnimationState;
  dragging?: boolean;
  lookDirection?: PetLookDirection | null;
  className?: string;
  onClick?: () => void;
  onDoubleClick?: () => void;
  onBodyDrag?: (dragging: boolean, direction: PetLookDirection | null) => void;
}) {
  const [clip, setClip] = useState<PetClip>(state);
  const [step, setStep] = useState(0);
  const [ready, setReady] = useState(false);
  const [waving, setWaving] = useState(false);
  const [bodyDragging, setBodyDragging] = useState(false);
  const [bodyLook, setBodyLook] = useState<PetLookDirection | null>(null);
  const flavourIndex = useRef(0);
  const flavourStarted = useRef(false);
  const waveTimer = useRef<number | null>(null);
  const pointer = useRef<{
    id: number;
    startX: number;
    startY: number;
    lastX: number;
    lastY: number;
    dragging: boolean;
  } | null>(null);

  const isDragging = dragging || bodyDragging;
  const look = bodyDragging ? bodyLook : lookDirection;
  const set = PET_FRAME_SETS[clip] ?? PET_FRAME_SETS.idle;
  const atlas = usesSpriteAtlas();
  // Pet motion is the product; do not gate on prefers-reduced-motion.
  const canPlayIdleFlavour = !waving && !isDragging && state === 'idle';

  useEffect(() => {
    let alive = true;
    preloadPetArt().then(() => {
      if (alive) setReady(true);
    });
    return () => {
      alive = false;
      if (waveTimer.current) window.clearTimeout(waveTimer.current);
    };
  }, []);

  // Sync clip from external state / drag, without stomping an active idle flavour.
  useEffect(() => {
    if (waving) return;
    if (isDragging) {
      const next = dragClipFor(look);
      setClip((current) => (current === next ? current : next));
      setStep(0);
      return;
    }
    setClip((current) => {
      if (state === 'idle' && isIdleFlavour(current)) return current;
      return current === state ? current : state;
    });
  }, [isDragging, look, state, waving]);

  // Schedule peek / sleep / stretch while truly idle.
  useEffect(() => {
    if (!canPlayIdleFlavour || clip !== 'idle') return;
    const delay = flavourStarted.current
      ? IDLE_FLAVOUR_MIN_MS + Math.floor(Math.random() * IDLE_FLAVOUR_JITTER_MS)
      : IDLE_FLAVOUR_FIRST_MS;
    const timer = window.setTimeout(() => {
      flavourStarted.current = true;
      const next = IDLE_FLAVOUR_CLIPS[flavourIndex.current % IDLE_FLAVOUR_CLIPS.length];
      flavourIndex.current += 1;
      setClip(next);
      setStep(0);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [canPlayIdleFlavour, clip]);

  // Frame playback for the active clip.
  useEffect(() => {
    if (!atlas || set.frames.length <= 1) {
      setStep(0);
      return;
    }
    setStep(0);
    const timer = window.setInterval(() => {
      setStep((current) => {
        const next = current + 1;
        if (next < set.frames.length) return next;
        if (set.loop) return 0;
        if (isIdleFlavour(clip) && !isDragging && !waving) {
          window.setTimeout(() => {
            setClip('idle');
            setStep(0);
          }, 0);
        }
        return current;
      });
    }, set.frameMs);
    return () => window.clearInterval(timer);
  }, [atlas, clip, isDragging, set.frameMs, set.frames.length, set.loop, waving]);

  const frame = set.frames[Math.min(step, set.frames.length - 1)] ?? set.frames[0] ?? 0;
  const interactive = Boolean(onClick || onDoubleClick || onBodyDrag);

  function finishBodyDrag() {
    if (!pointer.current) return;
    const wasDragging = pointer.current.dragging;
    pointer.current = null;
    if (wasDragging) {
      setBodyDragging(false);
      setBodyLook(null);
      onBodyDrag?.(false, null);
    }
  }

  function handlePointerDown(event: React.PointerEvent) {
    if (event.button !== 0 || waving) return;
    if (!window.desktop?.movePetBy && !onBodyDrag && !onClick) return;
    pointer.current = {
      id: event.pointerId,
      startX: event.screenX,
      startY: event.screenY,
      lastX: event.screenX,
      lastY: event.screenY,
      dragging: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: React.PointerEvent) {
    const track = pointer.current;
    if (!track || track.id !== event.pointerId) return;
    const dx = event.screenX - track.lastX;
    const dy = event.screenY - track.lastY;
    const totalX = event.screenX - track.startX;
    const totalY = event.screenY - track.startY;
    if (!track.dragging) {
      if (Math.hypot(totalX, totalY) < DRAG_THRESHOLD) return;
      track.dragging = true;
      setBodyDragging(true);
      const direction = lookFromDelta(totalX, totalY) ?? 'right';
      setBodyLook(direction);
      onBodyDrag?.(true, direction);
    }
    if (Math.abs(dx) >= 1 || Math.abs(dy) >= 1) {
      window.desktop?.movePetBy?.(Math.round(dx), Math.round(dy));
      const direction = lookFromDelta(dx, dy) ?? lookFromDelta(totalX, totalY);
      if (direction) {
        setBodyLook(direction);
        onBodyDrag?.(true, direction);
      }
      track.lastX = event.screenX;
      track.lastY = event.screenY;
    }
  }

  function handlePointerUp(event: React.PointerEvent) {
    const track = pointer.current;
    if (!track || track.id !== event.pointerId) return;
    const wasDragging = track.dragging;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* already released */
    }
    finishBodyDrag();
    if (!wasDragging) triggerWaveClick(event);
  }

  function triggerWaveClick(event: React.MouseEvent | React.KeyboardEvent | React.PointerEvent) {
    event.stopPropagation();
    if (!onClick || waving || isDragging) return;
    if (!atlas) {
      onClick();
      return;
    }
    const wave = PET_FRAME_SETS.wave;
    const duration = wave.frames.length * wave.frameMs;
    setWaving(true);
    setClip('wave');
    setStep(0);
    if (waveTimer.current) window.clearTimeout(waveTimer.current);
    waveTimer.current = window.setTimeout(() => {
      setWaving(false);
      setClip(state);
      setStep(0);
      onClick();
    }, duration);
  }

  return (
    <span
      className={`pet-character dog-${clip} ${className}`.trim()}
      data-state={state}
      data-clip={clip}
      data-dragging={isDragging ? 'true' : 'false'}
      data-look={look || undefined}
      data-animation-mode={atlas ? 'sprite-atlas' : 'temporary-layers'}
      data-ready={ready ? 'true' : 'false'}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? '桌面小狗豆豆' : undefined}
      title={interactive ? '按住身体可拖动；单击先挥手再开聊天' : undefined}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={finishBodyDrag}
      onDoubleClick={onDoubleClick}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                triggerWaveClick(event);
              }
            }
          : undefined
      }
    >
      <span
        className="pet-sprite"
        style={{
          backgroundImage: `url(${PET_ATLAS})`,
          backgroundPosition: atlasBackgroundPosition(frame),
        }}
        aria-hidden="true"
      />
    </span>
  );
}
