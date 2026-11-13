import { useEffect, useRef } from 'react';
import { PET_WINDOW_WIDTH } from './types';

/** Observe pet root height and resize the Electron window while anchoring the bottom edge. */
export function usePetWindowLayout(chatOpen: boolean) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;

    const publish = () => {
      const height = Math.ceil(node.getBoundingClientRect().height + 4);
      window.desktop?.resizePet(PET_WINDOW_WIDTH, height);
    };

    publish();
    const observer = new ResizeObserver(() => publish());
    observer.observe(node);
    return () => observer.disconnect();
  }, [chatOpen]);

  useEffect(() => {
    // Whole pet shell must receive mouse events so the bone cursor overlay can track.
    // Transparent pixels *outside* the shell still click through to the desktop.
    const move = (event: MouseEvent) => {
      const el = event.target instanceof Element ? event.target : null;
      const overPet = Boolean(el?.closest('[data-pet-shell], [data-interactive]'));
      window.desktop?.setPetClickThrough(!overPet);
    };
    window.addEventListener('mousemove', move, true);
    return () => window.removeEventListener('mousemove', move, true);
  }, []);

  return rootRef;
}
