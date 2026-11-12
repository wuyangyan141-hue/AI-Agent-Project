import { useEffect, useRef } from 'react';
import boneCursorUrl from '../assets/bone-cursor.png';
import boneCurUrl from '../assets/bone-cursor.cur';

const HOTSPOT = { x: 3, y: 3 };

/**
 * Transparent Electron windows on Windows often keep drawing the OS cursor.
 * Apply a real .CUR via CSS, and also paint a bone <img> that tracks the pointer.
 */
export function useBoneCursor(enabled = true) {
  const layerRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    if (!enabled) return;
    const layer = layerRef.current;
    if (!layer) return;

    const shell = layer.closest('[data-pet-shell]') as HTMLElement | null;
    const cssValue = `url(${JSON.stringify(boneCurUrl)}) ${HOTSPOT.x} ${HOTSPOT.y}, url(${JSON.stringify(boneCursorUrl)}) ${HOTSPOT.x} ${HOTSPOT.y}, crosshair`;
    const applyCursor = (node: HTMLElement | null) => {
      if (!node) return;
      node.style.setProperty('cursor', cssValue, 'important');
      node.classList.add('bone-cursor-on');
    };
    applyCursor(document.documentElement);
    applyCursor(document.body);
    applyCursor(shell);
    for (const node of Array.from(document.querySelectorAll<HTMLElement>('.pet-shell, .pet-shell *'))) {
      if (node.matches('textarea, input')) {
        node.style.setProperty('cursor', 'text', 'important');
      } else {
        node.style.setProperty('cursor', cssValue, 'important');
      }
    }

    const move = (event: MouseEvent) => {
      const target = event.target as Element | null;
      if (target?.closest?.('textarea, input, [data-no-bone-cursor]')) {
        layer.style.opacity = '0';
        return;
      }
      const host = (layer.offsetParent as HTMLElement | null) ?? shell;
      const rect = (host ?? document.documentElement).getBoundingClientRect();
      layer.style.opacity = '1';
      layer.style.transform = `translate(${event.clientX - rect.left - HOTSPOT.x}px, ${event.clientY - rect.top - HOTSPOT.y}px)`;
    };

    const hide = () => {
      layer.style.opacity = '0';
    };

    window.addEventListener('mousemove', move, true);
    window.addEventListener('blur', hide);
    return () => {
      window.removeEventListener('mousemove', move, true);
      window.removeEventListener('blur', hide);
      for (const node of [document.documentElement, document.body, shell]) {
        node?.classList.remove('bone-cursor-on');
        node?.style.removeProperty('cursor');
      }
    };
  }, [enabled]);

  return { layerRef, boneCursorUrl, hotspot: HOTSPOT };
}
