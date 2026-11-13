import { useEffect, useRef } from 'react';
import { api } from '../knowledge';

export type FocusStatus = {
  id: number | null;
  task_id?: number | null;
  task_title?: string | null;
  duration_minutes?: number;
  remaining_seconds: number;
  ends_at?: string;
};

export type FocusFinishResult = {
  id: number;
  finished?: boolean;
  task_id?: number | null;
  speech?: string | null;
  offer_review?: boolean;
  reward?: {
    speech?: string;
    message?: string;
    bones?: number;
    bones_earned?: number;
    streak?: { bones?: number; feed_cost?: number };
  } | null;
  streak?: { bones?: number; feed_cost?: number };
};

/**
 * Poll the active focus timer, report ticks, and auto-finish when time is up.
 */
export function useFocusReminder(handlers: {
  onTick?: (status: FocusStatus) => void;
  onFinished?: (result: FocusFinishResult) => void;
}) {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;
  const finishing = useRef(false);
  const handled = useRef(new Set<number>());

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      if (cancelled || finishing.current) return;
      try {
        const response = await fetch(`${api}/focus`);
        if (!response.ok) return;
        const status = (await response.json()) as FocusStatus;
        if (!cancelled) handlersRef.current.onTick?.(status);

        const id = status?.id;
        if (!id || status.remaining_seconds > 0) return;
        if (handled.current.has(id)) return;

        finishing.current = true;
        handled.current.add(id);
        try {
          const finish = await fetch(`${api}/focus/${id}/finish`, { method: 'POST' });
          if (cancelled) return;
          // 404 means another path (e.g. early finish) already closed the session.
          if (finish.ok) {
            const result = (await finish.json()) as FocusFinishResult;
            handlersRef.current.onFinished?.(result);
          }
        } finally {
          finishing.current = false;
        }
      } catch {
        finishing.current = false;
      }
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);
}
