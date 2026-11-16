import type { LearningNextStep } from './knowledge';

export type CareTimelineStatus = 'done' | 'overdue' | 'due' | 'upcoming';

export type CareTimelineItem = {
  id: string;
  title: string;
  status: CareTimelineStatus;
  dueLabel: string;
  completedLabel?: string;
  kind: 'task' | 'suggestion';
  taskId?: number;
};

const statusWord: Record<CareTimelineStatus, string> = {
  done: '已完成',
  overdue: '逾期',
  due: '今日',
  upcoming: '待办',
};

export function careStatusLabel(status: CareTimelineStatus): string {
  return statusWord[status];
}

type Task = {
  id: number;
  title: string;
  done: boolean;
  scheduled_day: number | null;
};

export function buildLearningCareItems(tasks: Task[], nextStep: LearningNextStep | null): CareTimelineItem[] {
  const items: CareTimelineItem[] = [];

  if (nextStep?.title) {
    items.push({
      id: 'next-step',
      kind: 'suggestion',
      title: nextStep.title,
      status: 'due',
      dueLabel: nextStep.suggestion?.slice(0, 48) || '学习助手建议',
    });
  }

  const sorted = [...tasks].sort((a, b) => {
    const da = a.scheduled_day ?? 9999;
    const db = b.scheduled_day ?? 9999;
    if (da !== db) return da - db;
    return a.id - b.id;
  });

  const open = sorted.filter((t) => !t.done);
  const focusDay = open.length
    ? Math.min(...open.map((t) => (t.scheduled_day == null ? 9999 : t.scheduled_day)))
    : null;

  for (const task of sorted) {
    const dueLabel =
      task.scheduled_day != null ? `计划 · 第 ${task.scheduled_day} 天` : '未排期';
    let status: CareTimelineStatus = 'upcoming';
    if (task.done) {
      status = 'done';
    } else if (focusDay != null && task.scheduled_day != null) {
      if (task.scheduled_day < focusDay) status = 'overdue';
      else if (task.scheduled_day === focusDay) status = 'due';
      else status = 'upcoming';
    } else if (focusDay === 9999 && open[0]?.id === task.id) {
      status = 'due';
    } else if (open[0]?.id === task.id) {
      status = 'due';
    }

    items.push({
      id: `task-${task.id}`,
      kind: 'task',
      taskId: task.id,
      title: task.title,
      status,
      dueLabel,
      completedLabel: task.done ? '已打卡' : undefined,
    });
  }

  return items;
}

export function filterCareItems(items: CareTimelineItem[], filter: 'all' | 'open' | 'overdue'): CareTimelineItem[] {
  if (filter === 'all') return items;
  if (filter === 'overdue') return items.filter((item) => item.status === 'overdue');
  return items.filter((item) => item.status !== 'done');
}

export function countCompletedTasks(items: CareTimelineItem[]): { done: number; total: number } {
  const taskItems = items.filter((i) => i.kind === 'task');
  const done = taskItems.filter((i) => i.status === 'done').length;
  return { done, total: taskItems.length };
}

/** 无任务/建议时仍展示学习路线结构，避免空白 */
export function fallbackCareItems(): CareTimelineItem[] {
  return [
    {
      id: 'hint-library',
      kind: 'suggestion',
      title: '加入学习资料',
      status: 'due',
      dueLabel: '侧栏展开学习夹 → 上传或从资料库加入',
    },
    {
      id: 'hint-plan',
      kind: 'suggestion',
      title: '生成学习计划',
      status: 'upcoming',
      dueLabel: '任务页创建计划，或聊天里说学习目标',
    },
  ];
}