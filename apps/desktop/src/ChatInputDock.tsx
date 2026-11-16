import type React from 'react';
import { HitlPanel } from './HitlPanel';
import type { PendingHitl } from './chatStore';
import type { KnowledgeDocument } from './knowledge';
import type { HitlKind } from './protocol';

type PlanDraft = {
  id: number;
  steps?: { day: number; title: string; minutes: number }[];
  schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[];
};

type Props = {
  connection: string;
  sending: boolean;
  input: string;
  setInput: (v: string) => void;
  scope: string;
  setScope: (v: string) => void;
  documents: KnowledgeDocument[];
  sharedDocCount: number;
  send: (e: React.FormEvent) => void;
  sendText: (text: string) => void;
  pendingHitl: PendingHitl | null;
  submitHitl: (payload: Record<string, string | number>, action?: string) => void;
  cancelHitl: () => void;
  sessionId: string | null;
  days: number;
  setDays: (n: number) => void;
  dailyMinutes: number;
  setDailyMinutes: (n: number) => void;
  planFromChat: () => void;
  draft: PlanDraft | null;
};

/** 聊天输入区：固定在主区域最底部 */
export function ChatInputDock({
  connection,
  sending,
  input,
  setInput,
  scope,
  setScope,
  documents,
  sharedDocCount,
  send,
  sendText,
  pendingHitl,
  submitHitl,
  cancelHitl,
  sessionId,
  days,
  setDays,
  dailyMinutes,
  setDailyMinutes,
  planFromChat,
  draft,
}: Props) {
  return (
    <div className="app-chat-dock">
      {pendingHitl && (
        <HitlPanel
          schema={pendingHitl.hitl}
          kind={pendingHitl.kind as HitlKind}
          interruptId={pendingHitl.interruptId}
          requestId={pendingHitl.requestId}
          sessionId={sessionId}
          disabled={connection !== '已连接'}
          onSubmit={submitHitl}
          onCancel={cancelHitl}
        />
      )}

      <div className="chat-quick-reviews" role="group" aria-label="一键学习">
        {(['今日计划', '今日小测', '薄弱点回顾', '开始复习'] as const).map((label) => (
          <button
            key={label}
            type="button"
            className="pp-btn pp-btn--quiet pp-btn--compact"
            disabled={sending || connection !== '已连接'}
            onClick={() => sendText(label)}
          >
            {label}
          </button>
        ))}
      </div>

      <form className="chat-composer" onSubmit={send}>
        <textarea
          aria-label="消息"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="问问资料里的内容，或告诉豆豆你的学习计划…"
          maxLength={4000}
          rows={2}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              sendText(input);
            }
          }}
        />
        <div className="composer-bottom">
          <select aria-label="资料检索范围" value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="auto">自动 · 知识与学习助手</option>
            <option value="chat">普通聊天 · 不查知识库</option>
            <option value="all">全部知识库</option>
            {scope === 'selection' && <option value="selection">已选 {sharedDocCount} 份资料</option>}
            {documents
              .filter((d) => d.status === 'ready' && !d.needs_reindex)
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                </option>
              ))}
          </select>
          <button
            type="submit"
            className="pp-btn pp-btn--primary"
            disabled={connection !== '已连接' || sending || !input.trim()}
            aria-live="polite"
          >
            {sending ? '思考中…' : '发送'}
          </button>
        </div>
      </form>

      <details className="plan-options plan-options-dock">
        <summary>把输入作为学习目标生成计划</summary>
        <div className="controls">
          <label>
            计划天数
            <input
              aria-label="聊天计划天数"
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
              aria-label="聊天每日分钟"
              type="number"
              min={15}
              max={240}
              value={dailyMinutes}
              onChange={(e) => setDailyMinutes(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            onClick={planFromChat}
            disabled={!input.trim() || input.trim().length > 200 || sending || connection !== '已连接'}
          >
            生成待确认草稿
          </button>
        </div>
      </details>
      {draft ? <p className="muted chat-draft-hint">计划草稿在上方对话区，确认后保存为任务。</p> : null}
    </div>
  );
}