import { useMemo, useState } from 'react';
import {
  countCompletedTasks,
  filterCareItems,
  type CareTimelineItem,
} from './careTimeline';
import { PawprintBadge } from './PawprintBadge';
import { PawprintButton } from './PawprintButton';

type Filter = 'all' | 'open' | 'overdue';

const filterOptions: { key: Filter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'open', label: '未完成' },
  { key: 'overdue', label: '逾期' },
];

type Props = {
  title: string;
  subtitle?: string;
  items: CareTimelineItem[];
  streakDays?: number;
  onPrimaryAction?: () => void;
  primaryActionLabel?: string;
  primaryDisabled?: boolean;
  onMarkTaskDone?: (taskId: number) => void;
  onUndoTaskDone?: (taskId: number) => void;
  onEditTask?: (taskId: number) => void;
  onDeleteTask?: (taskId: number) => void;
  compact?: boolean;
  docked?: boolean;
  onDismiss?: () => void;
};

export function LearningCareTimeline({
  title,
  subtitle,
  items,
  streakDays,
  onPrimaryAction,
  primaryActionLabel,
  primaryDisabled,
  onMarkTaskDone,
  onUndoTaskDone,
  onEditTask,
  onDeleteTask,
  compact,
  docked,
  onDismiss,
}: Props) {
  const [filter, setFilter] = useState<Filter>('all');
  const { done, total } = useMemo(() => countCompletedTasks(items), [items]);
  const visible = useMemo(() => filterCareItems(items, filter), [items, filter]);

  return (
    <section
      className={`pp-care-panel pp-care-timeline-widget${compact ? ' pp-care-panel--compact' : ''}${
        docked ? ' pp-care-panel--docked' : ''
      }`}
      data-component="learning-route"
      aria-label={title}
    >
      {onDismiss ? (
        <PawprintButton
          type="button"
          variant="quiet"
          compact
          className="pp-care-dismiss"
          aria-label="关闭学习路线"
          onClick={onDismiss}
        >
          ×
        </PawprintButton>
      ) : null}
      <header className="pp-care-head">
        <div>
          <h3 className="pp-care-title">{title}</h3>
          {subtitle ? <p className="pp-care-sub">{subtitle}</p> : null}
        </div>
        {total > 0 ? (
          <p className="pp-care-summary" aria-live="polite">
            {done} / {total} 任务已完成
            {streakDays ? ` · 连续 ${streakDays} 天` : ''}
          </p>
        ) : null}
      </header>

      <div className="pp-care-toolbar">
        <div className="pp-segment" role="group" aria-label="学习路线筛选">
          {filterOptions.map((opt) => (
            <button
              key={opt.key}
              type="button"
              className={filter === opt.key ? 'is-active' : ''}
              aria-pressed={filter === opt.key}
              onClick={() => setFilter(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {onPrimaryAction && primaryActionLabel ? (
          <PawprintButton variant="primary" compact disabled={primaryDisabled} onClick={onPrimaryAction}>
            {primaryActionLabel}
          </PawprintButton>
        ) : null}
      </div>

      {visible.length === 0 ? (
        <p className="pp-care-empty">
          {filter === 'overdue' ? '没有逾期项。可切换到「全部」查看记录。' : '暂无条目。'}
        </p>
      ) : (
        <ol className="pp-care-timeline pp-l-care">
          {visible.map((item) => (
            <li
              key={item.id}
              className={`pp-care-entry is-${item.status}${item.kind === 'suggestion' ? ' is-suggestion' : ''}${
                item.status === 'overdue' ? ' is-late' : ''
              }`}
            >
              <div className="pp-care-entry-head">
                <h4 className="pp-care-entry-title">{item.title}</h4>
                <PawprintBadge status={item.status} />
              </div>
              <p className="pp-care-meta">
                <span>{item.dueLabel}</span>
                {item.completedLabel ? <span className="pp-care-completed"> · {item.completedLabel}</span> : null}
              </p>
              {item.kind === 'task' && item.taskId != null ? (
                <div className="pp-care-actions pp-l-actions">
                  {item.status === 'done' ? (
                    <PawprintButton variant="quiet" compact onClick={() => onUndoTaskDone?.(item.taskId!)}>
                      标为未完成
                    </PawprintButton>
                  ) : (
                    <PawprintButton variant="secondary" compact onClick={() => onMarkTaskDone?.(item.taskId!)}>
                      标记完成
                    </PawprintButton>
                  )}
                  <PawprintButton variant="quiet" compact onClick={() => onEditTask?.(item.taskId!)}>
                    修改
                  </PawprintButton>
                  <PawprintButton variant="danger" compact onClick={() => onDeleteTask?.(item.taskId!)}>
                    删除
                  </PawprintButton>
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}