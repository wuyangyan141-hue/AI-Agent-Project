import { useEffect, useRef, useState } from 'react';
import { messageEvent, parseServerEvent } from '../protocol';
import { mapServerEventToPet } from './stateMapping';
import { conversation, useConversation, scopeFields } from '../chatStore';
import {
  DEFAULT_BUBBLE_COPY,
  ERROR_HOLD_MS,
  bubbleHoldMs,
  type ChatLine,
  type ConnectionPhase,
  type PetAnimationState,
} from './types';

const endpoint = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/chat';
const SYNC_CHANNEL = 'learning-companion-chat-sync';

type SyncPayload =
  | { kind: 'session'; sessionId: string | null }
  | { kind: 'lines'; lines: ChatLine[] };

export function usePetSocket() {
  const [connection, setConnection] = useState<ConnectionPhase>('connecting');
  const [animation, setAnimation] = useState<PetAnimationState>('idle');
  const [bubbleText, setBubbleText] = useState(DEFAULT_BUBBLE_COPY.idle);
  const [sending, setSending] = useState(false);
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
      if (!petBus.current) petBus.current = new BroadcastChannel('learning-companion-pet');
      petBus.current.postMessage(event);
    }
  }

  function applyTerminalHold(next: PetAnimationState, text: string) {
    if (holdTimer.current) window.clearTimeout(holdTimer.current);
    if (next !== 'success' && next !== 'error') return;
    const holdMs = bubbleHoldMs(text, next === 'error' ? 'error' : 'success');
    holdTimer.current = window.setTimeout(() => {
      setAnimation('idle');
      setBubbleText(DEFAULT_BUBBLE_COPY.idle);
      publishLocal('idle', DEFAULT_BUBBLE_COPY.idle);
    }, holdMs);
  }

  useEffect(() => {
    let cancelled = false;

    const handleMessage = (raw: string) => {
      try {
        const data = parseServerEvent(raw);
        if(data.type==='welcome')return;
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
    const {state,text}=shared.status;
    setAnimation(state);setBubbleText(text);
    if(state==='success'||state==='error')applyTerminalHold(state,text);
  },[shared.status?.state,shared.status?.text]);

  function sendText(text: string) {
    const trimmed = text.trim();
    const live = socket.current;
    if (!trimmed || sendingRef.current || !live || live.readyState !== WebSocket.OPEN) return false;
    const current=conversation.getSnapshot();
    const requestId=conversation.begin(trimmed);
    if(!requestId)return false;
    live.send(JSON.stringify({...JSON.parse(messageEvent(trimmed)),session_id:current.sessionId,request_id:requestId,...scopeFields(current.scope)}));
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
  };
}
