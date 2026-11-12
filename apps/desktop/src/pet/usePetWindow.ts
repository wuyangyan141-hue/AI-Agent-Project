import { useEffect, useRef } from 'react';
import { PET_WINDOW_WIDTH } from './types';

/** Observe pet root height and resize the Electron window while anchoring the bottom edge. */
export function usePetWindowLayout(chatOpen: boolean) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = rootRef.current;
    if (!node) return;

    const publish = () => {
      const height = Math.ceil(node.getBoundingClientRect().height + 12);
      window.desktop?.resizePet(PET_WINDOW_WIDTH, height);
    };

    publish();
    const observer = new ResizeObserver(() => publish());
    observer.observe(node);
    return () => observer.disconnect();
  }, [chatOpen]);

  useEffect(() => {
    const move = (event: MouseEvent) => {
      window.desktop?.setPetClickThrough(!(event.target instanceof Element && event.target.closest('[data-interactive]')));
    };
    window.addEventListener('mousemove', move);
    return () => window.removeEventListener('mousemove', move);
  }, []);

  return rootRef;
}
