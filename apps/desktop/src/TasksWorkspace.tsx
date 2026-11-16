import { PawprintButton } from './PawprintButton';
type PlanDraft = {
  id: number;
  steps?: { day: number; title: string; minutes: number }[];
  schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[];
  reason?: string;
};

type Task = {
  id: number;
  title: string;
  done: boolean;
  estimated_minutes: number;
  scheduled_day: number | null;
  bones_awarded?: boolean;
};

type StreakInfo = {
  current_streak?: number;
  achievements?: string[];
  achievement_labels?: string[];
  total_focus_minutes?: number;
  bones?: number;
  tasks_completed?: number;
  feed_cost?: number;
};

type Props = {
  streak: StreakInfo | null;
  goal: string;
  setGoal: (v: string) => void;
  days: number;
  setDays: (v: number) => void;
  dailyMinutes: number;
  setDailyMinutes: (v: number) => void;
  draft: PlanDraft | null;
  setDraft: (v: PlanDraft | null) => void;
  createDraft: (kind: 'plan' | 'replan') => void;
  confirmDraft: () => void;
  taskTitle: string;
  setTaskTitle: (v: string) => void;
  addTask: (e: React.FormEvent) => void;
  feedPetWithBones: () => void;
  trash: Task[];
  showTrash: boolean;
  setShowTrash: (v: boolean | ((p: boolean) => boolean)) => void;
  restoreTask: (task: Task) => void;
  purgeTask: (task: Task) => void;
  planTaskCount: number;
  onDeleteLearningPlan: () => void;
};

export function TasksWorkspace({
  streak,
  goal,
  setGoal,
  days,
  setDays,
  dailyMinutes,
  setDailyMinutes,
  draft,
  setDraft,
  createDraft,
  confirmDraft,
  taskTitle,
  setTaskTitle,
  addTask,
  feedPetWithBones,
  trash,
  showTrash,
  setShowTrash,
  restoreTask,
  purgeTask,
  planTaskCount,
  onDeleteLearningPlan,
}: Props) {
  return (
    <section className="page-card tasks-workspace">
      <h2>学习计划</h2>
      <p className="streak-banner">
        骨头 {streak?.bones || 0} · 已完成任务 {streak?.tasks_completed || 0}
        {streak?.current_streak ? ` · 连续学习 ${streak.current_streak} 天` : ''} · 累计专注{' '}
        {streak?.total_focus_minutes || 0} 分钟
        {(streak?.achievement_labels || streak?.achievements || []).length
          ? ` · 成就：${(streak?.achievement_labels || streak?.achievements || []).join('、')}`
          : ''}
      </p>
      <div className="bones-shop">
        <p className="muted">
          骨头用途：每个任务只能领一次。攒够后可花 {streak?.feed_cost || 3} 根喂豆豆，换一句鼓励并让桌宠开心一下。
        </p>
        <PawprintButton
          variant="secondary"
          disabled={(streak?.bones || 0) < (streak?.feed_cost || 3)}
          onClick={feedPetWithBones}
        >
          喂豆豆（{streak?.feed_cost || 3} 骨头）
        </PawprintButton>
      </div>
      <div className="controls">
        <input
          aria-label="学习目标"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="例如：复习数据库索引"
        />
        <label>
          天数
          <input
            aria-label="计划天数"
            type="number"
            min={1}
            max={14}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          />
        </label>
        <label>
          每天分钟
          <input
            aria-label="每日分钟"
            type="number"
            min={15}
            max={240}
            value={dailyMinutes}
            onChange={(e) => setDailyMinutes(Number(e.target.value))}
          />
        </label>
      </div>
      <div className="controls pp-l-actions">
        <PawprintButton variant="primary" disabled={!goal.trim()} onClick={() => createDraft('plan')}>
          生成新计划
        </PawprintButton>
        <PawprintButton variant="secondary" onClick={() => createDraft('replan')}>
          重新安排未完成任务
        </PawprintButton>
        <PawprintButton
          variant="danger"
          disabled={planTaskCount === 0}
          title={planTaskCount === 0 ? '当前没有已保存的学习计划' : undefined}
          onClick={onDeleteLearningPlan}
        >
          删除学习计划{planTaskCount > 0 ? `（${planTaskCount}）` : ''}
        </PawprintButton>
      </div>
      {draft ? (
        <div className="draft">
          <h3>计划草稿（尚未保存）</h3>
          <p>{draft.reason}</p>
          <ol>
            {(draft.steps || draft.schedule || []).map((step, i) => (
              <li key={i}>
                第 {step.day} 天 · {step.title} · {step.minutes} 分钟
              </li>
            ))}
          </ol>
          <div className="pp-l-actions">
            <PawprintButton variant="primary" onClick={confirmDraft}>
              确认并保存
            </PawprintButton>
            <PawprintButton variant="quiet" onClick={() => setDraft(null)}>
              取消
            </PawprintButton>
          </div>
        </div>
      ) : null}

      <p className="muted tasks-route-hint">学习任务在底部「学习路线」中管理：标记完成、修改或删除。</p>

      <form className="tasks-add-form" onSubmit={addTask}>
        <input
          aria-label="新任务"
          value={taskTitle}
          onChange={(e) => setTaskTitle(e.target.value)}
          placeholder="手动添加单条任务，例如：复习数据库索引"
          maxLength={200}
        />
        <PawprintButton type="submit" variant="secondary" compact>
          添加任务
        </PawprintButton>
      </form>

      <div className="trash-panel">
        <PawprintButton variant="quiet" compact className="trash-toggle" onClick={() => setShowTrash((v) => !v)}>
          回收站{trash.length ? `（${trash.length}）` : ''}
          {showTrash ? ' ▾' : ' ▸'}
        </PawprintButton>
        {showTrash &&
          (trash.length ? (
            <ul className="task-list trash-list">
              {trash.map((task) => (
                <li key={task.id}>
                  <span className="trash-title">
                    {task.title} · {task.estimated_minutes} 分钟
                    {task.scheduled_day ? ` · 第 ${task.scheduled_day} 天` : ''}
                    {task.done ? ' · 已完成' : ''}
                  </span>
                  <PawprintButton variant="secondary" compact onClick={() => restoreTask(task)}>
                    恢复
                  </PawprintButton>
                  <PawprintButton variant="danger" compact onClick={() => purgeTask(task)}>
                    永久删除
                  </PawprintButton>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted trash-empty">回收站是空的。</p>
          ))}
      </div>
    </section>
  );
}