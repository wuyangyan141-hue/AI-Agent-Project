import React, { useEffect, useRef } from 'react';
import type { ChatLine } from './types';
import { conversation } from '../chatStore';

/** Bubble-thread transcript above the pet (keeps speech-bubble look). */
export function PetChatLog({
  messages,
  liveText,
  sending = false,
  onOpenFullChat,
  onAnswer,
}: {
  messages: ChatLine[];
  liveText?: string;
  sending?: boolean;
  onOpenFullChat: () => void;
  onAnswer?: (text: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const lines = messages.slice(-12);
  const live = (liveText || '').trim();
  const showLive = Boolean(live) && (!lines.length || lines[lines.length - 1]?.content !== live);
  const latest = [...lines].reverse().find((line) => line.role === 'assistant');
  const waitingReview = latest?.metadata?.review;
  const latestIdx = latest ? lines.findIndex((line) => line.id === latest.id) : -1;
  const answeredAfter = latestIdx >= 0 && lines.slice(latestIdx + 1).some((line) => line.role === 'user');
  const canPick = Boolean(
    onAnswer
    && !sending
    && !answeredAfter
    && waitingReview?.options?.length
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [lines, showLive, liveText, canPick]);

  return (
    <div className="pet-bubble-thread" data-interactive aria-label="桌宠对话气泡">
      <div className="pet-bubble-thread-scroll">
        {!lines.length && !showLive && (
          <div className="pet-bubble pet-bubble-mini">
            <p className="pet-bubble-text">问资料问题，或点「出题」开始答题～</p>
            <span className="pet-bubble-arrow" aria-hidden="true" />
          </div>
        )}
        {lines.map((line) => {
          const isLatestReview = canPick && latest?.id === line.id;
          const options = isLatestReview ? waitingReview?.options || [] : [];
          return (
            <div
              key={line.id}
              className={`pet-bubble pet-bubble-mini ${line.role === 'user' ? 'pet-bubble-user' : 'pet-bubble-assistant'}`}
            >
              <span className="pet-bubble-who">{line.role === 'user' ? '你' : '豆豆'}</span>
              <p className="pet-bubble-text">{line.content}</p>
              {line.metadata?.warning && <small>{line.metadata.warning}</small>}
              {!!options.length && (
                <div className="pet-review-options" role="group" aria-label="答题选项">
                  {options.map((option) => (
                    <button
                      key={option.key}
                      type="button"
                      disabled={sending}
                      onClick={() => onAnswer?.(option.key)}
                    >
                      <span>{option.key}</span>
                      {option.text}
                    </button>
                  ))}
                </div>
              )}
              {!!line.metadata?.sources?.length && (
                <div className="pet-citations">
                  {line.metadata.sources.map((source) => (
                    <button
                      type="button"
                      key={source.id}
                      onClick={() => {
                        conversation.update({ openCitation: { token: crypto.randomUUID(), source } });
                        onOpenFullChat();
                      }}
                    >
                      [{source.id}] {source.filename}
                      {source.page ? ` · ${source.page}页` : ''}
                    </button>
                  ))}
                </div>
              )}
              <span className="pet-bubble-arrow" aria-hidden="true" />
            </div>
          );
        })}
        {showLive && (
          <div className="pet-bubble pet-bubble-mini pet-bubble-assistant pet-bubble-live">
            <span className="pet-bubble-who">豆豆</span>
            <p className="pet-bubble-text">{live}</p>
            <span className="pet-bubble-arrow" aria-hidden="true" />
          </div>
        )}
        <div ref={endRef} />
      </div>
      <button type="button" className="pet-bubble-more" onClick={onOpenFullChat}>
        打开完整聊天窗口
      </button>
    </div>
  );
}
