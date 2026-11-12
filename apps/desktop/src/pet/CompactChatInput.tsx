import React, { type FormEvent, type KeyboardEvent, useState } from 'react';
import { canSendMessage } from './stateMapping';
import type { ConnectionPhase } from './types';

export function CompactChatInput({
  connection,
  sending,
  onSend,
  onCancelSending,
}: {
  connection: ConnectionPhase;
  sending: boolean;
  onSend: (text: string) => boolean;
  onCancelSending?: () => void;
}) {
  const [value, setValue] = useState('');
  const enabled = canSendMessage(connection, value, sending);

  function armClick() {
    window.desktop?.setPetClickThrough?.(false);
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    armClick();
    if (!enabled) return;
    if (onSend(value)) setValue('');
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  const blockedReason =
    connection !== 'connected'
      ? '未连接后端，发送不可用'
      : sending
        ? '正在等待回复…'
        : !value.trim()
          ? '输入内容后即可发送'
          : '';

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
        placeholder={connection === 'connected' ? '在桌面直接说……' : '连接中，稍后再试……'}
        maxLength={500}
        disabled={connection !== 'connected'}
        aria-label="桌面聊天输入"
      />
      <div className="pet-chat-actions">
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
