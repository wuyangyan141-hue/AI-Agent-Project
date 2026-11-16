import { LearningCareTimeline } from './LearningCareTimeline';
import type { CareTimelineItem } from './careTimeline';

type Props = {
  petName: string;
  items: CareTimelineItem[];
  open: boolean;
  onDismiss: () => void;
  onOpen: () => void;
  streakDays?: number;
  onPrimaryAction?: () => void;
  primaryActionLabel?: string;
  primaryDisabled?: boolean;
  onMarkTaskDone: (id: number) => void;
  onUndoTaskDone: (id: number) => void;
  onEditTask: (id: number) => void;
  onDeleteTask: (id: number) => void;
  nextStepSuggestion?: string;
};

/** 全局学习路线：各页底部公用同一组件，可关闭 */
export function GlobalCareRail({
  petName,
  items,
  open,
  onDismiss,
  onOpen,
  streakDays,
  onPrimaryAction,
  primaryActionLabel,
  primaryDisabled,
  onMarkTaskDone,
  onUndoTaskDone,
  onEditTask,
  onDeleteTask,
  nextStepSuggestion,
}: Props) {
  if (!open) {
    return (
      <div className="app-global-dock app-global-dock--collapsed">
        <button type="button" className="pp-btn pp-btn--quiet pp-btn--compact" onClick={onOpen}>
          显示学习路线
        </button>
      </div>
    );
  }

  return (
    <div className="app-global-dock">
      <LearningCareTimeline
        title={`${petName} · 学习路线`}
        subtitle={nextStepSuggestion || '计划任务与今日建议'}
        items={items}
        streakDays={streakDays}
        onPrimaryAction={onPrimaryAction}
        primaryActionLabel={primaryActionLabel}
        primaryDisabled={primaryDisabled}
        onMarkTaskDone={onMarkTaskDone}
        onUndoTaskDone={onUndoTaskDone}
        onEditTask={onEditTask}
        onDeleteTask={onDeleteTask}
        compact
        docked
        onDismiss={onDismiss}
      />
    </div>
  );
}