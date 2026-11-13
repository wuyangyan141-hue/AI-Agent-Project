import React from 'react';
import { BUBBLE_MAX_LINES } from './types';
import type { PlanOption, ReviewChoice, TodayPlanTask } from '../knowledge';

export function isBubbleTruncated(text: string, maxLines = BUBBLE_MAX_LINES): boolean {
  const lines = text.replace(/\r/g, '').split('\n');
  if (lines.length > maxLines) return true;
  // Approximate CJK width: ~16 chars per line in the pet bubble.
  const approxLines = lines.reduce((sum, line) => sum + Math.max(1, Math.ceil(line.length / 16)), 0);
  return approxLines > maxLines;
}

function formatRemain(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function PetBubble({
  text,
  options,
  tasks,
  planOptions,
  confirmingTask,
  activeFocus,
  offerReview = false,
  sending = false,
  historyExpanded = false,
  onAnswer,
  onSelectTask,
  onChoosePlan,
  onDismissPlan,
  onReselectPlan,
  onStartCheckIn,
  onCancelCheckIn,
  onFinishEarly,
  onStartReview,
  onSkipReview,
  onToggleHistory,
  onOpenDesktopChat,
  onClose,
}: {
  text: string;
  options?: ReviewChoice[];
  tasks?: TodayPlanTask[];
  planOptions?: PlanOption[];
  confirmingTask?: TodayPlanTask | null;
  activeFocus?: {
    id: number;
    task_id?: number | null;
    title?: string | null;
    remaining_seconds: number;
    duration_minutes?: number;
  } | null;
  offerReview?: boolean;
  sending?: boolean;
  historyExpanded?: boolean;
  onAnswer?: (text: string) => void;
  onSelectTask?: (task: TodayPlanTask) => void;
  onChoosePlan?: (option: PlanOption) => void;
  onDismissPlan?: () => void;
  /** Back to 轻量/标准/加练 after already picking one. */
  onReselectPlan?: () => void;
  onStartCheckIn?: () => void;
  onCancelCheckIn?: () => void;
  onFinishEarly?: () => void;
  onStartReview?: () => void;
  onSkipReview?: () => void;
  /** Expand / collapse past turns above this bubble. */
  onToggleHistory?: () => void;
  onOpenDesktopChat?: () => void;
  onClose?: () => void;
}) {
  const openTasks = (tasks || []).filter((task) => task.id && !task.done);
  const longForm = Boolean(options?.length)
    || Boolean(openTasks.length)
    || Boolean(planOptions?.length)
    || Boolean(confirmingTask)
    || Boolean(activeFocus)
    || offerReview
    || text.length > 72
    || text.includes('\n');
  return (
    <div className="pet-bubble" data-interactive role="status" aria-live="polite">
      {onClose && (
        <button type="button" className="pet-bubble-close" aria-label="收起对话" title="收起对话" onClick={onClose}>
          ×
        </button>
      )}
      <p className={`pet-bubble-text${longForm ? ' is-scrollable' : ' pet-bubble-text-idle'}`}>{text}</p>
      {!!options?.length && onAnswer && (
        <div className="pet-review-options" role="group" aria-label="答题选项">
          {options.map((option) => (
            <button
              key={option.key}
              type="button"
              disabled={sending}
              onClick={() => onAnswer(option.key)}
            >
              <span>{option.key}</span>
              {option.text}
            </button>
          ))}
        </div>
      )}
      {activeFocus && (
        <div className="pet-checkin-card" role="group" aria-label="打卡计时中">
          <p className="pet-checkin-title">{activeFocus.title || '专注打卡中'}</p>
          <p className="pet-checkin-timer" aria-live="polite">{formatRemain(activeFocus.remaining_seconds)}</p>
          <p className="pet-checkin-tip">到点自动领骨头 · 提前可说「我做完了」</p>
          {onFinishEarly && (
            <button type="button" className="pet-checkin-primary" disabled={sending} onClick={onFinishEarly}>
              我做完了
            </button>
          )}
        </div>
      )}
      {!activeFocus && offerReview && (onStartReview || onSkipReview) && (
        <div className="pet-checkin-card" role="group" aria-label="巩固复习">
          <p className="pet-checkin-label">打卡完成</p>
          <p className="pet-checkin-title">要不要出一题巩固？</p>
          <div className="pet-checkin-actions">
            {onSkipReview && (
              <button type="button" className="pet-checkin-secondary" disabled={sending} onClick={onSkipReview}>
                稍后再说
              </button>
            )}
            {onStartReview && (
              <button type="button" className="pet-checkin-primary" disabled={sending} onClick={onStartReview}>
                出一题
              </button>
            )}
          </div>
        </div>
      )}
      {!activeFocus && !offerReview && confirmingTask && (
        <div className="pet-checkin-card" role="group" aria-label="确认打卡内容">
          <p className="pet-checkin-label">确认打卡内容</p>
          <p className="pet-checkin-title">{confirmingTask.title}</p>
          {!!confirmingTask.estimated_minutes && (
            <p className="pet-checkin-tip">约 {confirmingTask.estimated_minutes} 分钟</p>
          )}
          <p className="pet-checkin-tip">要改就跟我说，或去完整窗口。</p>
          <div className="pet-checkin-actions">
            {onCancelCheckIn && (
              <button type="button" className="pet-checkin-secondary" disabled={sending} onClick={onCancelCheckIn}>
                换一项
              </button>
            )}
            {onStartCheckIn && (
              <button type="button" className="pet-checkin-primary" disabled={sending} onClick={onStartCheckIn}>
                开始打卡
              </button>
            )}
          </div>
          {onReselectPlan && (
            <button type="button" className="pet-plan-dismiss" disabled={sending} onClick={onReselectPlan}>
              返回三选一
            </button>
          )}
        </div>
      )}
      {!activeFocus && !offerReview && !confirmingTask && !!planOptions?.length && onChoosePlan && (
        <div className="pet-plan-options" role="group" aria-label="选择今日计划">
          {planOptions.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => onChoosePlan(option)}
            >
              <span className="pet-plan-label">{option.label}</span>
              <span className="pet-plan-blurb">{option.blurb || `${option.minutes || ''} 分钟`}</span>
            </button>
          ))}
          {onDismissPlan && (
            <button type="button" className="pet-plan-dismiss" onClick={onDismissPlan}>
              先不选，返回对话
            </button>
          )}
        </div>
      )}
      {!activeFocus && !offerReview && !confirmingTask && !!openTasks.length && onSelectTask && (
        <div className="pet-today-tasks" role="group" aria-label="今日事办提醒">
          {openTasks.map((task) => (
            <button
              key={task.id}
              type="button"
              disabled={sending}
              title="点一下确认打卡内容"
              onClick={() => onSelectTask(task)}
            >
              <span className="pet-today-check" aria-hidden="true">☐</span>
              <span className="pet-today-title">{task.title}</span>
              {!!task.estimated_minutes && (
                <span className="pet-today-mins">{task.estimated_minutes}分</span>
              )}
            </button>
          ))}
          {onReselectPlan && (
            <button type="button" className="pet-plan-dismiss" disabled={sending} onClick={onReselectPlan}>
              返回三选一
            </button>
          )}
        </div>
      )}
      <div className="pet-bubble-actions">
        {onToggleHistory && (
          <button type="button" className="pet-bubble-more" onClick={onToggleHistory}>
            {historyExpanded ? '收起历史' : '展开历史'}
          </button>
        )}
        {onOpenDesktopChat && (
          <button type="button" className="pet-bubble-more quiet" onClick={onOpenDesktopChat}>
            完整窗口
          </button>
        )}
        {onClose && (
          <button type="button" className="pet-bubble-more quiet" onClick={onClose}>
            收起对话
          </button>
        )}
      </div>
      <span className="pet-bubble-arrow" aria-hidden="true" />
    </div>
  );
}
