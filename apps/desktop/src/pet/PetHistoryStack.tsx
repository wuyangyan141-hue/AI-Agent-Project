import React, { useEffect, useRef } from 'react';
import type { ChatLine } from './types';

/** Past turns stacked above the single live bubble on the pet. */
export function PetHistoryStack({
  messages,
  currentText,
}: {
  messages: ChatLine[];
  /** Hide the duplicate of whatever the live bubble is already showing. */
  currentText?: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const live = (currentText || '').trim();
  const history = messages
    .slice(-10)
    .filter((line) => line.content.trim() && line.content.trim() !== live);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [history.length, live]);

  if (!history.length) {
    return (
      <div className="pet-history-stack" data-interactive aria-label="历史对话">
        <p className="pet-history-empty">还没有更早的对话。</p>
      </div>
    );
  }

  return (
    <div className="pet-history-stack" data-interactive aria-label="历史对话">
      <div className="pet-history-scroll">
        {history.map((line) => (
          <div
            key={line.id}
            className={`pet-history-item ${line.role === 'user' ? 'is-user' : 'is-assistant'}`}
          >
            <span className="pet-history-who">{line.role === 'user' ? '你' : '豆豆'}</span>
            <p>{line.content}</p>
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
