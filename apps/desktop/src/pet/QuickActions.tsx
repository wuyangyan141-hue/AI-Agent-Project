import React from 'react';

export function QuickActions({
  chatOpen,
  onToggleChat,
  onOpenLibrary,
}: {
  chatOpen: boolean;
  onToggleChat: () => void;
  onOpenLibrary: () => void;
}) {
  return (
    <div className="pet-quick" data-interactive>
      <button type="button" onClick={onOpenLibrary}>
        知识库
      </button>
      <span aria-hidden="true">·</span>
      <button type="button" onClick={onToggleChat}>
        {chatOpen ? '收起聊天' : '聊一聊'}
      </button>
    </div>
  );
}
