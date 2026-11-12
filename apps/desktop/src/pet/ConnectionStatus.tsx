import React from 'react';
import type { ConnectionPhase } from './types';

const labels: Record<ConnectionPhase, string> = {
  connecting: '正在连接',
  connected: '已连接',
  disconnected: '连接断开',
};

export function ConnectionStatus({ phase }: { phase: ConnectionPhase }) {
  return (
    <div className={`pet-connection pet-connection-${phase}`} data-interactive aria-live="polite">
      <span className="pet-connection-dot" aria-hidden="true" />
      <span>{labels[phase]}</span>
    </div>
  );
}
