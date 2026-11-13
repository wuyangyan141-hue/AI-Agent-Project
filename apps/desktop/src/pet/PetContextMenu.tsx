import React, { useEffect, useState } from 'react';

export function PetContextMenu({
  onOpenChat,
  onOpenLibrary,
  onToggleChat,
  onClosePet,
  onRestartPet,
  onTodayPlan,
  onContinueReview,
  onFeedPet,
  onAsk,
  onQuiz,
  onWeakPoint,
  feedLabel = '喂骨头',
  feedDisabled = false,
  chatOpen,
  restartShortcut = 'Ctrl+Shift+R',
}: {
  onOpenChat: () => void;
  onOpenLibrary: () => void;
  onToggleChat: () => void;
  onClosePet: () => void;
  onRestartPet: () => void;
  onTodayPlan: () => void;
  onContinueReview: () => void;
  onFeedPet?: () => void;
  onAsk?: () => void;
  onQuiz?: () => void;
  onWeakPoint?: () => void;
  feedLabel?: string;
  feedDisabled?: boolean;
  chatOpen: boolean;
  restartShortcut?: string;
}) {
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const onContext = (event: MouseEvent) => {
      if (!(event.target instanceof Element) || !event.target.closest('[data-pet-shell]')) return;
      if (event.target.closest('.pet-context-menu')) return;
      event.preventDefault();
      setMenu({ x: event.clientX, y: event.clientY });
    };
    const dismiss = (event: MouseEvent) => {
      if (event.target instanceof Element && event.target.closest('.pet-context-menu')) return;
      setMenu(null);
    };
    window.addEventListener('contextmenu', onContext);
    window.addEventListener('pointerdown', dismiss);
    return () => {
      window.removeEventListener('contextmenu', onContext);
      window.removeEventListener('pointerdown', dismiss);
    };
  }, []);

  function run(action: () => void) {
    setMenu(null);
    // Defer so the menu unmount does not cancel the IPC/open side effect.
    window.setTimeout(action, 0);
  }

  if (!menu) return null;
  return (
    <div
      className="pet-context-menu"
      data-interactive
      style={{ left: menu.x, top: menu.y }}
      role="menu"
      onPointerDown={(event) => event.stopPropagation()}
      onContextMenu={(event) => event.preventDefault()}
    >
      {onAsk && (
        <button type="button" role="menuitem" onClick={() => run(onAsk)}>
          提问
        </button>
      )}
      {onQuiz && (
        <button type="button" role="menuitem" onClick={() => run(onQuiz)}>
          出题答题
        </button>
      )}
      {onWeakPoint && (
        <button type="button" role="menuitem" onClick={() => run(onWeakPoint)}>
          薄弱点回顾
        </button>
      )}
      <button type="button" role="menuitem" onClick={() => run(onTodayPlan)}>
        今日计划
      </button>
      <button type="button" role="menuitem" onClick={() => run(onContinueReview)}>
        继续复习
      </button>
      {onFeedPet && (
        <button type="button" role="menuitem" disabled={feedDisabled} onClick={() => run(onFeedPet)}>
          {feedLabel}
        </button>
      )}
      <button type="button" role="menuitem" onClick={() => run(onOpenChat)}>
        打开完整聊天
      </button>
      <button type="button" role="menuitem" onClick={() => run(onOpenLibrary)}>
        打开知识库
      </button>
      <button type="button" role="menuitem" onClick={() => run(onToggleChat)}>
        {chatOpen ? '收起头顶历史' : '展开头顶历史'}
      </button>
      <button type="button" role="menuitem" onClick={() => run(onRestartPet)}>
        重启桌宠（{restartShortcut}）
      </button>
      <button type="button" role="menuitem" onClick={() => run(onClosePet)}>
        隐藏
      </button>
    </div>
  );
}
