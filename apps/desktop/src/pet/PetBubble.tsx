import React from 'react';
import { BUBBLE_MAX_LINES } from './types';

export function isBubbleTruncated(text: string, maxLines = BUBBLE_MAX_LINES): boolean {
  const lines = text.replace(/\r/g, '').split('\n');
  if (lines.length > maxLines) return true;
  // Approximate CJK width: ~16 chars per line in the pet bubble.
  const approxLines = lines.reduce((sum, line) => sum + Math.max(1, Math.ceil(line.length / 16)), 0);
  return approxLines > maxLines;
}

export function PetBubble({
  text,
  onOpenFullChat,
}: {
  text: string;
  onOpenFullChat?: () => void;
}) {
  return (
    <div className="pet-bubble" data-interactive role="status" aria-live="polite">
      <p className="pet-bubble-text pet-bubble-text-idle">{text}</p>
      {onOpenFullChat && (
        <button type="button" className="pet-bubble-more" onClick={onOpenFullChat}>
          打开聊天
        </button>
      )}
      <span className="pet-bubble-arrow" aria-hidden="true" />
    </div>
  );
}
