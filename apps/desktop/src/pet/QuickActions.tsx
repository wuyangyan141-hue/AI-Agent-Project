import React from 'react';

export function QuickActions({
  chatOpen,
  onToggleChat,
  onOpenLibrary,
  onFeedPet,
  onAsk,
  onQuiz,
  onWeakPoint,
  onTodayPlan,
  bones = 0,
  feedCost = 3,
  feeding = false,
}: {
  chatOpen: boolean;
  onToggleChat: () => void;
  onOpenLibrary: () => void;
  onFeedPet?: () => void;
  onAsk?: () => void;
  onQuiz?: () => void;
  onWeakPoint?: () => void;
  onTodayPlan?: () => void;
  bones?: number;
  feedCost?: number;
  feeding?: boolean;
}) {
  const canFeed = Boolean(onFeedPet) && !feeding && bones >= feedCost;
  return (
    <div className="pet-quick" data-interactive>
      {onTodayPlan && (
        <button type="button" title="查看今天的学习任务" onClick={onTodayPlan}>
          今日计划
        </button>
      )}
      {onAsk && (
        <button type="button" onClick={onAsk}>
          提问
        </button>
      )}
      {onQuiz && (
        <button type="button" onClick={onQuiz}>
          出题
        </button>
      )}
      {onWeakPoint && (
        <button type="button" title="根据近期错题/薄弱点出一题" onClick={onWeakPoint}>
          薄弱点
        </button>
      )}
      <button type="button" onClick={onOpenLibrary}>
        知识库
      </button>
      <button type="button" onClick={onToggleChat}>
        {chatOpen ? '收起历史' : '展开历史'}
      </button>
      {onFeedPet && (
        <button
          type="button"
          title={canFeed ? `花 ${feedCost} 根骨头喂豆豆（剩余 ${bones}）` : `骨头不足：需要 ${feedCost}，当前 ${bones}`}
          disabled={!canFeed}
          onClick={onFeedPet}
        >
          {feeding ? '喂食中…' : `骨头 ${bones}`}
        </button>
      )}
    </div>
  );
}
