import React, { type FormEvent, type KeyboardEvent, useState } from 'react';
import { canSendMessage } from './stateMapping';
import type { ConnectionPhase } from './types';

export function CompactChatInput({
  connection,
  sending,
  onSend,
}: {
  connection: ConnectionPhase;
  sending: boolean;
  onSend: (text: string) => boolean;
}) {
  const [value, setValue] = useState('');
  const enabled = canSendMessage(connection, value, sending);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!enabled) return;
    if (onSend(value)) setValue('');
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="pet-chat-form" data-interactive onSubmit={submit}>
      <textarea
        value={value}
        rows={1}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="在桌面直接说……"
        maxLength={500}
        disabled={connection !== 'connected' || sending}
        aria-label="桌面聊天输入"
      />
      <button type="submit" disabled={!enabled}>
        发送
      </button>
    </form>
  );
}
