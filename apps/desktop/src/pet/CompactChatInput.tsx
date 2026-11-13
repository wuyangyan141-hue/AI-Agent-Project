import React, { type FormEvent, type KeyboardEvent, type PointerEvent, useRef, useState } from 'react';
import { canSendMessage } from './stateMapping';
import type { ConnectionPhase } from './types';
import { useSpeechInput } from './useSpeechInput';

export function CompactChatInput({
  connection,
  sending,
  onSend,
  onCancelSending,
  placeholder,
}: {
  connection: ConnectionPhase;
  sending: boolean;
  onSend: (text: string) => boolean;
  onCancelSending?: () => void;
  placeholder?: string;
}) {
  const [value, setValue] = useState('');
  const valueRef = useRef(value);
  valueRef.current = value;
  const holdPointer = useRef<number | null>(null);
  const baseBeforeTalk = useRef('');
  const enabled = canSendMessage(connection, value, sending);

  const speech = useSpeechInput((text, isFinal) => {
    const prefix = baseBeforeTalk.current.trim();
    const next = prefix ? `${prefix} ${text}` : text;
    setValue(next.slice(0, 500));
    if (isFinal) valueRef.current = next.slice(0, 500);
  });

  function armClick() {
    window.desktop?.setPetClickThrough?.(false);
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    armClick();
    if (!canSendMessage(connection, valueRef.current, sending)) return;
    if (onSend(valueRef.current)) {
      setValue('');
      valueRef.current = '';
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  function beginTalk(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || connection !== 'connected' || sending || !speech.supported) return;
    armClick();
    holdPointer.current = event.pointerId;
    baseBeforeTalk.current = valueRef.current;
    event.currentTarget.setPointerCapture(event.pointerId);
    speech.start();
  }

  function endTalk(event: PointerEvent<HTMLButtonElement>) {
    if (holdPointer.current !== event.pointerId) return;
    holdPointer.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* ignore */
    }
    speech.stop();
    // Push-to-talk: release sends the recognized text when possible.
    window.setTimeout(() => {
      const text = valueRef.current.trim();
      if (!text || sending || connection !== 'connected') return;
      if (onSend(text)) {
        setValue('');
        valueRef.current = '';
      }
    }, 180);
  }

  const blockedReason =
    connection !== 'connected'
      ? '未连接后端，发送不可用'
      : sending
        ? '正在等待回复…'
        : speech.listening
          ? '正在听…松开发送'
          : speech.error
            ? speech.error
            : !value.trim()
              ? speech.supported
                ? '输入或按住麦克风说话'
                : '输入内容后即可发送'
              : '';

  const micTitle = !speech.supported
    ? '当前环境不支持语音识别'
    : connection !== 'connected'
      ? '连接后端后可用'
      : sending
        ? '等待回复中'
        : speech.listening
          ? '松开发送'
          : '按住说话，松开发送';

  return (
    <form
      className="pet-chat-form"
      data-interactive
      onSubmit={submit}
      onPointerDown={armClick}
      onMouseEnter={armClick}
    >
      <textarea
        value={value}
        rows={2}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        onFocus={armClick}
        placeholder={
          speech.listening
            ? '正在听…'
            : connection === 'connected'
              ? (placeholder || '提问 / 答题，或按住麦克风说……')
              : '连接中，稍后再试……'
        }
        maxLength={500}
        disabled={connection !== 'connected'}
        aria-label="桌面聊天输入"
      />
      <div className="pet-chat-actions">
        <button
          type="button"
          className={`pet-chat-mic${speech.listening ? ' is-listening' : ''}`}
          disabled={!speech.supported || connection !== 'connected' || sending}
          title={micTitle}
          aria-label={micTitle}
          onPointerDown={beginTalk}
          onPointerUp={endTalk}
          onPointerCancel={endTalk}
        >
          {speech.listening ? '听' : '麦'}
        </button>
        {sending && onCancelSending ? (
          <button type="button" className="pet-chat-cancel" onClick={onCancelSending}>
            取消
          </button>
        ) : null}
        <button type="submit" disabled={!enabled} title={blockedReason || '发送'}>
          {sending ? '…' : '发送'}
        </button>
      </div>
      {blockedReason && (
        <p className="pet-chat-hint" role="status">
          {blockedReason}
        </p>
      )}
    </form>
  );
}
