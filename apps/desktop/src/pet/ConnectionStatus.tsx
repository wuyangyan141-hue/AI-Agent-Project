import React from 'react';
import type { ConnectionPhase } from './types';

const labels: Record<ConnectionPhase, string> = {
  connecting: '正在连接',
  connected: '已连接',
  disconnected: '连接断开',
};

export function ConnectionStatus({
  phase,
  compact = false,
}: {
  phase: ConnectionPhase;
  compact?: boolean;
}) {
  return (
    <div
      className={`pet-connection pet-connection-${phase}${compact ? ' is-compact' : ''}`}
      data-interactive
      aria-live="polite"
      title={labels[phase]}
    >
      <span className="pet-connection-dot" aria-hidden="true" />
      {!compact && <span>{labels[phase]}</span>}
    </div>
  );
}
