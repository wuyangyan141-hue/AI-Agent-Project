import React from 'react';
import type { ChatMessage, Source } from './knowledge';
import { messageShowsRagSources, sourcePosition } from './knowledge';
type PlanDraft = {
  id: number;
  steps?: { day: number; title: string; minutes: number }[];
  schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[];
};

type Props = {
  petName: string;
  messages: ChatMessage[];
  sending: boolean;
  connection: string;
  activity: string;
  setInput: (v: string) => void;
  onOpenLibrary: () => void;
  transcriptRef: React.RefObject<HTMLElement | null>;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  sendText: (text: string) => void;
  setSource: (s: Source) => void;
  draft: PlanDraft | null;
  setDraft: (next: PlanDraft | null) => void;
  confirmDraft: () => void;
};

export function ChatWorkspace({
  petName,
  messages,
  sending,
  connection,
  activity,
  setInput,
  onOpenLibrary,
  transcriptRef,
  messagesEndRef,
  sendText,
  setSource,
  draft,
  setDraft,
  confirmDraft,
}: Props) {
  return (
    <div className="chat-workspace">
      <section ref={transcriptRef as React.RefObject<HTMLElement>} className="chat-transcript" aria-label="对话记录">
        {messages.length === 0 ? (
          <div className="chat-greeting">
            <h2 className="chat-empty-title">开始对话</h2>
            <p>提问、做计划或小测；有资料时回答会附可核对出处。</p>
            <div className="greeting-actions">
              <p className="muted" style={{ width: '100%', margin: 0 }}>
                在左侧学习夹展开后，可上传或加入资料。
              </p>
              <button type="button" className="pp-btn pp-btn--secondary" onClick={onOpenLibrary}>
                打开资料库
              </button>
              <button
                type="button"
                className="pp-btn pp-btn--quiet pp-btn--compact"
                onClick={() => setInput('帮我制定复习数据库的学习计划，3天每天30分钟')}
              >
                示例：三天学习计划
              </button>
            </div>
          </div>
        ) : (
          messages.map((message) => {
            const showSources = messageShowsRagSources(message.metadata?.mode, message.metadata?.sources);
            return (
            <article className={`chat-message ${message.role}`} key={message.id}>
              <ChatSpeaker message={message} petName={petName} />
              {message.metadata?.warning && <p className="answer-warning">{message.metadata.warning}</p>}
              <div className="chat-content">
                {message.content.split(/(\[S\d+\])/g).map((part, i) => {
                  const citation = showSources
                    ? message.metadata?.sources?.find((s) => `[${s.id}]` === part)
                    : undefined;
                  return citation ? (
                    <button className="citation-button" key={i} type="button" onClick={() => setSource(citation)}>
                      {part}
                    </button>
                  ) : (
                    <React.Fragment key={i}>{part}</React.Fragment>
                  );
                })}
              </div>
              {showSources && (
                <div className="source-pills">
                  {message.metadata!.sources!.map((s) => (
                    <button key={s.id} type="button" onClick={() => setSource(s)}>
                      <span>{s.id}</span>
                      {s.filename} · {sourcePosition(s)}
                    </button>
                  ))}
                </div>
              )}
              {!!message.metadata?.review?.options?.length &&
                (message.metadata.mode === 'review' || message.metadata.mode === 'review_question') && (
                  <div className="chat-review-options" role="group" aria-label="选择题选项">
                    {message.metadata.review.options.map((option) => (
                      <button
                        key={option.key}
                        type="button"
                        disabled={sending || connection !== '已连接'}
                        onClick={() => sendText(option.key)}
                      >
                        {option.key}. {option.text}
                      </button>
                    ))}
                  </div>
                )}
            </article>
            );
          })
        )}
        {sending && (
          <p className="thinking-line">
            <span />
            {activity || '豆豆正在思考…'}
          </p>
        )}
        {draft && (
          <div className="draft draft-in-transcript">
            <h3>待确认的计划草稿</h3>
            <ol>
              {(draft.steps || draft.schedule || []).map((step, i) => (
                <li key={i}>
                  第 {step.day} 天 · {step.title} · {step.minutes} 分钟
                </li>
              ))}
            </ol>
            <button type="button" onClick={confirmDraft}>
              确认并保存任务
            </button>
            <button type="button" className="quiet" onClick={() => setDraft(null)}>
              取消
            </button>
          </div>
        )}
        <div ref={messagesEndRef} />
      </section>
    </div>
  );
}

const MODE_LABELS: Record<string, string> = {
  memory: '个人记忆',
  overview: '全文摘要',
  summary: '全文摘要',
  extractive_overview: '全文摘要',
  comparison: '资料比较',
  general: '普通聊天',
  review: '复习反馈',
  review_feedback: '复习反馈',
  review_question: '复习题',
  llm: '依据资料回答',
  clarification: '需要说明',
  no_evidence: '资料不足',
  agent: '学习助手',
  plan_revise: '计划草稿',
  plan_draft: '计划草稿',
  today_plan: '今日计划',
};

function ChatSpeaker({ message, petName }: { message: ChatMessage; petName: string }) {
  const mode = message.metadata?.mode;
  const modeLabel = mode ? MODE_LABELS[mode] || '检索原文' : null;
  return (
    <div className="chat-speaker">
      {message.role === 'user' ? '你' : petName}
      {modeLabel && (
        <span className="answer-mode pp-badge pp-badge--upcoming">
          <span className="pp-badge-dot" aria-hidden="true" />
          {modeLabel}
        </span>
      )}
    </div>
  );
}