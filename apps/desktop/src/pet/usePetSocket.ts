import { useEffect, useRef, useState } from 'react';
import { messageEvent, parseServerEvent } from '../protocol';
import { mapServerEventToPet } from './stateMapping';
import { conversation, useConversation, scopeFields } from '../chatStore';
import { request, type PlanOption, type TodayPlanTask } from '../knowledge';
import { useFocusReminder, type FocusFinishResult, type FocusStatus } from './useFocusReminder';
import {
  DEFAULT_BUBBLE_COPY,
  ERROR_HOLD_MS,
  bubbleHoldMs,
  isPetAnimationState,
  type ChatLine,
  type ConnectionPhase,
  type PetAnimationState,
} from './types';

export type ActiveCheckIn = {
  id: number;
  task_id?: number | null;
  title?: string | null;
  remaining_seconds: number;
  duration_minutes?: number;
  ends_at?: string;
};

const endpoint = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/chat';
const PET_BUS = 'learning-companion-pet';
const SYNC_CHANNEL = 'learning-companion-chat-sync';

type SyncPayload =
  | { kind: 'session'; sessionId: string | null }
  | { kind: 'lines'; lines: ChatLine[] };

export function usePetSocket() {
  const [connection, setConnection] = useState<ConnectionPhase>('connecting');
  const [animation, setAnimation] = useState<PetAnimationState>('idle');
  const [bubbleText, setBubbleText] = useState(DEFAULT_BUBBLE_COPY.idle);
  const [sending, setSending] = useState(false);
  const [bones, setBones] = useState(0);
  const [feedCost, setFeedCost] = useState(3);
  const [feeding, setFeeding] = useState(false);
  const [confirmingTask, setConfirmingTask] = useState<TodayPlanTask | null>(null);
  const [activeCheckIn, setActiveCheckIn] = useState<ActiveCheckIn | null>(null);
  const [offerReview, setOfferReview] = useState(false);
  const activeCheckInRef = useRef<ActiveCheckIn | null>(null);
  const rewardedFocus = useRef<number | null>(null);
  const shared=useConversation();
  const messages=shared.messages;
  const setMessages=conversation.setMessages;
  const socket = useRef<WebSocket | null>(null);
  const session = useRef<string | null>(null);
  const sync = useRef<BroadcastChannel | null>(null);
  const sendingRef = useRef(false);
  const reconnectTimer = useRef<number | null>(null);
  const holdTimer = useRef<number | null>(null);
  const sendWatchdog = useRef<number | null>(null);
  const intentionalClose = useRef(false);

  const petBus = useRef<BroadcastChannel | null>(null);

  function clearSending() {
    sendingRef.current = false;
    setSending(false);
    if (sendWatchdog.current) {
      window.clearTimeout(sendWatchdog.current);
      sendWatchdog.current = null;
    }
  }

  function armSendWatchdog() {
    if (sendWatchdog.current) window.clearTimeout(sendWatchdog.current);
    // Unlock the send button if the backend never finishes the turn.
    sendWatchdog.current = window.setTimeout(() => {
      if (!sendingRef.current) return;
      clearSending();
      setAnimation('error');
      setBubbleText('回复超时了，请再发一次。');
      publishLocal('error', '回复超时了，请再发一次。');
    }, 60000);
  }

  function publishLocal(animationState: PetAnimationState, text: string) {
    const event = { type: 'status', state: animationState, text };
    if (window.desktop) window.desktop.publishState(event);
    else {
      if (!petBus.current) petBus.current = new BroadcastChannel(PET_BUS);
      petBus.current.postMessage(event);
    }
  }

  function applyTerminalHold(next: PetAnimationState, text: string) {
    if (holdTimer.current) window.clearTimeout(holdTimer.current);
    if (next !== 'success' && next !== 'error' && next !== 'talking') return;
    const holdMs = bubbleHoldMs(text, next === 'error' ? 'error' : 'success');
    holdTimer.current = window.setTimeout(() => {
      setAnimation('idle');
      setBubbleText(DEFAULT_BUBBLE_COPY.idle);
      publishLocal('idle', DEFAULT_BUBBLE_COPY.idle);
    }, holdMs);
  }

  function applyExternalStatus(state: PetAnimationState, text: string) {
    let nextText = text.trim() || DEFAULT_BUBBLE_COPY[state] || DEFAULT_BUBBLE_COPY.idle;
    // Guard against the main panel echoing long welcome / review essays into the bubble.
    // Allow a bit more room for feed-pet cheers while still blocking essay dumps.
    const essay = /结合已上传资料|含义或作用|作答时尽量覆盖|请检查后确认保存/.test(nextText);
    if (essay || nextText.length > 48) {
      nextText = state === 'idle' ? DEFAULT_BUBBLE_COPY.idle : nextText.slice(0, 28) + '…';
    }
    setAnimation(state);
    setBubbleText(nextText);
    if (state === 'success' || state === 'error' || state === 'talking') applyTerminalHold(state, nextText);
  }

  function markTodayTaskDone(taskId: number | null | undefined) {
    if (!taskId) return;
    conversation.setMessages((msgs) => {
      const next = [...msgs];
      for (let i = next.length - 1; i >= 0; i -= 1) {
        const plan = next[i].metadata?.today_plan;
        if (!plan?.tasks?.length) continue;
        const tasks = plan.tasks.map((task) => (
          task.id === taskId ? { ...task, done: true } : task
        ));
        next[i] = {
          ...next[i],
          metadata: { ...next[i].metadata, today_plan: { ...plan, tasks } },
        };
        break;
      }
      return next;
    });
  }

  function applyCheckInReward(result: FocusFinishResult) {
    if (result.id && rewardedFocus.current === result.id) return;
    if (result.id) rewardedFocus.current = result.id;
    const reward = result.reward;
    const speech = (result.speech || reward?.speech || reward?.message || '打卡完成，骨头到手啦～').trim();
    if (reward?.streak?.bones != null) setBones(Number(reward.streak.bones) || 0);
    else if (reward?.bones != null) setBones(Number(reward.bones) || 0);
    else if (result.streak?.bones != null) setBones(Number(result.streak.bones) || 0);
    else void refreshBones();
    if (reward?.streak?.feed_cost) setFeedCost(Number(reward.streak.feed_cost) || feedCost);
    else if (result.streak?.feed_cost) setFeedCost(Number(result.streak.feed_cost) || feedCost);
    markTodayTaskDone(result.task_id);
    setConfirmingTask(null);
    setActiveCheckIn(null);
    setOfferReview(Boolean(result.task_id) || Boolean(result.offer_review));
    applyExternalStatus('talking', speech.split('\n')[0].slice(0, 40));
    conversation.setMessages((msgs) => [
      ...msgs,
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: speech,
        metadata: { mode: 'task_reward', offer_review: true },
      },
    ]);
  }

  useFocusReminder({
    onTick: (status: FocusStatus) => {
      if (!status?.id) {
        setActiveCheckIn((current) => {
          // Focus closed elsewhere (e.g. chat said「我做完了」) — sync pet UI once.
          if (current && rewardedFocus.current !== current.id) {
            rewardedFocus.current = current.id;
            if (current.task_id) markTodayTaskDone(current.task_id);
            void refreshBones();
            applyExternalStatus('talking', '打卡完成，骨头到手啦～');
          }
          return null;
        });
        return;
      }
      setActiveCheckIn((current) => ({
        id: status.id!,
        task_id: status.task_id ?? current?.task_id ?? null,
        title: status.task_title ?? current?.title ?? null,
        remaining_seconds: status.remaining_seconds,
        duration_minutes: status.duration_minutes ?? current?.duration_minutes,
        ends_at: status.ends_at,
      }));
    },
    onFinished: (result) => {
      applyCheckInReward(result);
    },
  });

  async function refreshBones() {
    try {
      const streak = await request<{ bones?: number; feed_cost?: number }>('/learning/streak');
      setBones(Number(streak.bones) || 0);
      setFeedCost(Number(streak.feed_cost) || 3);
    } catch {
      /* keep last known balance */
    }
  }

  useEffect(() => {
    activeCheckInRef.current = activeCheckIn;
  }, [activeCheckIn]);

  function isDoneUtterance(text: string): boolean {
    const t = text.trim();
    return /^(?:我)?做完了[。！!～]*$|我做完了|提前完成(?:了|打卡)?|打卡完成了?|完成打卡|结束打卡|结束专注|专注结束/.test(t);
  }

  function selectCheckInTask(task: TodayPlanTask) {
    if (!task?.id || activeCheckIn) return;
    setConfirmingTask(task);
    setBubbleFriendlyConfirm(task);
  }

  function setBubbleFriendlyConfirm(task: TodayPlanTask) {
    const mins = task.estimated_minutes || 25;
    applyExternalStatus('talking', `确认一下：${(task.title || '这项').slice(0, 16)}…约${mins}分`);
  }

  function cancelCheckIn() {
    setConfirmingTask(null);
  }

  async function startCheckIn() {
    const task = confirmingTask;
    if (!task?.id || activeCheckIn) return false;
    const minutes = Math.max(1, Number(task.estimated_minutes) || 25);
    try {
      const focus = await request<ActiveCheckIn & { started_at?: string }>('/focus', {
        method: 'POST',
        body: JSON.stringify({ task_id: task.id, minutes }),
      });
      setConfirmingTask(null);
      setActiveCheckIn({
        id: focus.id,
        task_id: focus.task_id ?? task.id,
        title: task.title,
        remaining_seconds: Math.max(1, Math.round(minutes * 60)),
        duration_minutes: minutes,
        ends_at: focus.ends_at,
      });
      applyExternalStatus('tool', `开始打卡啦，计时 ${minutes} 分钟～`);
      conversation.setMessages((msgs) => [
        ...msgs,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `好，按「${task.title}」开始打卡，计划 ${minutes} 分钟。到点我会喊你领骨头；要改内容随时跟我说。`,
          metadata: { mode: 'check_in_started', focus },
        },
      ]);
      return true;
    } catch (error) {
      const detail = error instanceof Error ? error.message : '开始打卡失败';
      applyExternalStatus('error', detail.slice(0, 28));
      return false;
    }
  }

  async function finishCheckInEarly() {
    const session = activeCheckIn;
    if (!session?.id) return false;
    try {
      const result = await request<FocusFinishResult>(`/focus/${session.id}/finish`, { method: 'POST' });
      applyCheckInReward({ ...result, task_id: result.task_id ?? session.task_id });
      return true;
    } catch (error) {
      const detail = error instanceof Error ? error.message : '结束打卡失败';
      applyExternalStatus('error', detail.slice(0, 28));
      return false;
    }
  }

  async function choosePlanOption(option: PlanOption) {
    if (!option?.id) return false;
    try {
      applyExternalStatus('tool', `正在保存「${option.label}」计划…`);
      const result = await request<{
        today_plan?: import('../knowledge').TodayPlanPayload;
      }>(`/plans/drafts/${option.id}/confirm?replace_open=true`, { method: 'POST' });
      setConfirmingTask(null);
      setOfferReview(false);
      const agenda = result.today_plan;
      const speech = agenda?.tasks?.length
        ? `好，已选「${option.label}」。选一项确认后开始打卡～`
        : `已保存「${option.label}」计划。`;
      applyExternalStatus('success', speech.slice(0, 40));
      conversation.setMessages((msgs) => [
        ...msgs,
        { id: crypto.randomUUID(), role: 'user', content: `选${option.label}` },
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: speech,
          metadata: {
            mode: 'today_plan',
            today_plan: agenda || { tasks: [], text: speech },
          },
        },
      ]);
      return true;
    } catch (error) {
      const detail = error instanceof Error ? error.message : '保存计划失败';
      // Stale draft ids after a previous silent apply — ask for a fresh 三选一.
      if (/已应用|already applied|409/i.test(detail) || detail.includes('Draft')) {
        applyExternalStatus('error', '这套已用过，再说「换一套计划」');
      } else {
        applyExternalStatus('error', detail.slice(0, 28));
      }
      return false;
    }
  }

  function startReviewOffer() {
    setOfferReview(false);
    return sendText('出题');
  }

  function skipReviewOffer() {
    setOfferReview(false);
    applyExternalStatus('idle', DEFAULT_BUBBLE_COPY.idle);
  }

  function dismissPlanOptions() {
    setConfirmingTask(null);
    setOfferReview(false);
    const speech = '好，先不选。继续聊天就行；想看计划再说「今日计划」或「换一套计划」。';
    applyExternalStatus('talking', speech.slice(0, 40));
    conversation.setMessages((msgs) => [
      ...msgs,
      { id: crypto.randomUUID(), role: 'user', content: '先不选' },
      {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: speech,
        metadata: { mode: 'general' },
      },
    ]);
  }

  function reselectPlanOptions() {
    setConfirmingTask(null);
    setOfferReview(false);
    return sendText('换一套计划');
  }

  async function feedPet() {
    if (feeding) return false;
    if (bones < feedCost) {
      applyExternalStatus('error', `骨头不够，还差 ${feedCost - bones} 根～`);
      return false;
    }
    setFeeding(true);
    try {
      const result = await request<{
        speech?: string;
        message?: string;
        bones?: number;
        streak?: { bones?: number; feed_cost?: number };
      }>('/learning/bones/feed', { method: 'POST' });
      const speech = (result.speech || result.message || '汪！好吃～').trim();
      const nextBones = Number(result.streak?.bones ?? result.bones ?? Math.max(0, bones - feedCost));
      setBones(nextBones);
      if (result.streak?.feed_cost) setFeedCost(Number(result.streak.feed_cost) || feedCost);
      applyExternalStatus('talking', speech);
      conversation.setMessages((msgs) => [
        ...msgs,
        { id: crypto.randomUUID(), role: 'assistant', content: speech, metadata: { mode: 'pet_feed' } },
      ]);
      conversation.update({ status: { state: 'talking', text: speech } });
      return true;
    } catch (error) {
      const detail = error instanceof Error ? error.message : '喂食失败';
      applyExternalStatus('error', detail.slice(0, 28));
      await refreshBones();
      return false;
    } finally {
      setFeeding(false);
    }
  }

  useEffect(() => {
    void refreshBones();
    const timer = window.setInterval(() => { void refreshBones(); }, 20000);
    return () => window.clearInterval(timer);
  }, []);

  // study_time → gently push today's agenda once per matching minute.
  useEffect(() => {
    let lastKey = '';
    const timer = window.setInterval(async () => {
      if (activeCheckInRef.current) return;
      try {
        const prefs = await request<Record<string, string>>('/knowledge/preferences');
        const match = (prefs.study_time || '').match(/(\d{1,2})\s*[:：]\s*(\d{2})/);
        if (!match) return;
        const now = new Date();
        const hour = Number(match[1]);
        const minute = Number(match[2]);
        if (now.getHours() !== hour || now.getMinutes() !== minute) return;
        const key = `${now.toDateString()}-${hour}:${minute}`;
        if (lastKey === key) return;
        lastKey = key;
        applyExternalStatus('talking', '到点啦！一起看今日事办～');
        conversation.setMessages((msgs) => [
          ...msgs,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: '到你的学习时段啦～点「今日计划」或直接说「今日计划」，豆豆陪你打卡。',
            metadata: { mode: 'study_reminder' },
          },
        ]);
      } catch {
        /* ignore */
      }
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const handleStatus = (payload: unknown) => {
      if (!payload || typeof payload !== 'object') return;
      const data = payload as { type?: string; state?: string; text?: string };
      if (data.type && data.type !== 'status') return;
      if (!data.state || !isPetAnimationState(data.state)) return;
      applyExternalStatus(data.state, typeof data.text === 'string' ? data.text : '');
    };

    const unsubscribe = window.desktop?.onPetState?.(handleStatus);
    let bus: BroadcastChannel | null = null;
    if (!window.desktop?.onPetState) {
      bus = new BroadcastChannel(PET_BUS);
      petBus.current = bus;
      bus.onmessage = (event) => handleStatus(event.data);
    }
    return () => {
      unsubscribe?.();
      bus?.close();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const handleMessage = (raw: string) => {
      try {
        const data = parseServerEvent(raw);
        if (data.type === 'welcome') {
          // Prefer a short title; never paste a full review prompt into the bubble.
          const title = data.next_step?.title?.trim();
          const short = title && title.length <= 28 ? `嗨～${title}` : DEFAULT_BUBBLE_COPY.idle;
          setAnimation('idle');
          setBubbleText(short);
          publishLocal('idle', short);
          return;
        }
        if(!conversation.receive(data))return;
        if(data.type==='status')armSendWatchdog();
        const mapped = mapServerEventToPet(data, sendingRef.current);
        setAnimation(mapped.animation);
        setBubbleText(mapped.bubbleText);
        publishLocal(mapped.animation, mapped.bubbleText);
        if (mapped.finished || data.type === 'reply' || data.type === 'error' || data.type === 'plan_draft') {
          clearSending();
          if (mapped.finished) applyTerminalHold(mapped.animation, mapped.bubbleText);
        }
      } catch {
        /* ignore malformed */
      }
    };

    const connect = () => {
      if (cancelled) return;
      setConnection('connecting');
      const ws = new WebSocket(endpoint);
      socket.current = ws;
      ws.onopen = () => {
        if (cancelled) return;
        setConnection('connected');
        clearSending();
        // Resume idle flavours after reconnect instead of staying on error/thinking.
        setAnimation('idle');
        setBubbleText(DEFAULT_BUBBLE_COPY.idle);
        publishLocal('idle', DEFAULT_BUBBLE_COPY.idle);
      };
      ws.onclose = () => {
        if (cancelled || intentionalClose.current) return;
        setConnection('disconnected');
        clearSending();
        setAnimation('error');
        setBubbleText(DEFAULT_BUBBLE_COPY.error);
        publishLocal('error', DEFAULT_BUBBLE_COPY.error);
        if (holdTimer.current) window.clearTimeout(holdTimer.current);
        holdTimer.current = window.setTimeout(() => {
          setAnimation('idle');
          setBubbleText(DEFAULT_BUBBLE_COPY.idle);
          publishLocal('idle', DEFAULT_BUBBLE_COPY.idle);
        }, ERROR_HOLD_MS);
        if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
        reconnectTimer.current = window.setTimeout(connect, 1800);
      };
      ws.onerror = () => undefined;
      ws.onmessage = (message) => handleMessage(String(message.data));
    };

    connect();
    return () => {
      cancelled = true;
      intentionalClose.current = true;
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
      if (holdTimer.current) window.clearTimeout(holdTimer.current);
      if (sendWatchdog.current) window.clearTimeout(sendWatchdog.current);
      socket.current?.close();


    };
  }, []);

  useEffect(()=>{sendingRef.current=Boolean(shared.pending);setSending(Boolean(shared.pending));},[shared.pending]);
  useEffect(()=>{
    if(!shared.status)return;
    applyExternalStatus(shared.status.state, shared.status.text);
  },[shared.status?.state,shared.status?.text]);

  function sendText(text: string, options?: { reviewAnswer?: boolean }) {
    const trimmed = text.trim();
    if (!trimmed || sendingRef.current) return false;
    // Scheme D: during timed check-in, saying「我做完了」finishes early without waiting for the clock.
    if (!options?.reviewAnswer && activeCheckInRef.current && isDoneUtterance(trimmed)) {
      conversation.setMessages((msgs) => [
        ...msgs,
        { id: crypto.randomUUID(), role: 'user', content: trimmed },
      ]);
      void finishCheckInEarly();
      return true;
    }
    // Leaving plan/check-in chrome so a normal chat like「你好」can show its reply.
    if (!options?.reviewAnswer) {
      setConfirmingTask(null);
      setOfferReview(false);
    }
    const live = socket.current;
    if (!live || live.readyState !== WebSocket.OPEN) return false;
    const current=conversation.getSnapshot();
    const requestId=conversation.begin(trimmed);
    if(!requestId)return false;
    const asReviewAnswer = Boolean(options?.reviewAnswer) || /^[A-Da-d]$/.test(trimmed);
    live.send(JSON.stringify({
      ...JSON.parse(messageEvent(trimmed)),
      session_id: current.sessionId,
      request_id: requestId,
      ...scopeFields(current.scope),
      ...(asReviewAnswer ? { review_answer: true } : {}),
    }));
    sendingRef.current = true;
    setSending(true);
    setConnection('connected');
    armSendWatchdog();
    setAnimation('thinking');
    setBubbleText(DEFAULT_BUBBLE_COPY.thinking);
    publishLocal('thinking', DEFAULT_BUBBLE_COPY.thinking);
    return true;
  }

  return {
    connection,
    animation,
    setAnimation,
    bubbleText,
    setBubbleText,
    sending,
    messages,
    sendText,
    clearSending,
    bones,
    feedCost,
    feeding,
    feedPet,
    confirmingTask,
    activeCheckIn,
    offerReview,
    selectCheckInTask,
    cancelCheckIn,
    startCheckIn,
    finishCheckInEarly,
    choosePlanOption,
    dismissPlanOptions,
    reselectPlanOptions,
    startReviewOffer,
    skipReviewOffer,
    refreshBones,
  };
}
