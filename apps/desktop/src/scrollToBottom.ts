/** Scroll a scrollable chat pane to the latest message (not the outer window). */
export function scrollToBottom(
  container: HTMLElement | null | undefined,
  options?: { smooth?: boolean; force?: boolean },
) {
  if (!container) return;
  const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
  const nearBottom = distance < 140;
  if (!options?.force && !nearBottom && container.dataset.userScrolled === '1') return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const smooth = Boolean(options?.smooth) && !reduceMotion;

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      if (smooth) {
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
      } else {
        container.scrollTop = container.scrollHeight;
      }
    });
  });
}

export function bindStickToBottom(container: HTMLElement | null | undefined) {
  if (!container) return () => {};
  const onScroll = () => {
    const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
    container.dataset.userScrolled = distance > 140 ? '1' : '0';
  };
  container.addEventListener('scroll', onScroll, { passive: true });
  return () => container.removeEventListener('scroll', onScroll);
}