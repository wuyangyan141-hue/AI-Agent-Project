import React, { useEffect, useRef, useState } from 'react';
import { lookFromDelta, type PetLookDirection } from './animationAssets';
import { CompactChatInput } from './CompactChatInput';
import { ConnectionStatus } from './ConnectionStatus';
import { PetBubble } from './PetBubble';
import { PetCharacter } from './PetCharacter';
import { PetContextMenu } from './PetContextMenu';
import { PetHistoryStack } from './PetHistoryStack';
import { QuickActions } from './QuickActions';
import { useBoneCursor } from './useBoneCursor';
import { usePetSocket } from './usePetSocket';
import { usePetWindowLayout } from './usePetWindow';
import { DEFAULT_BUBBLE_COPY } from './types';
import './pet-window.css';
import './pet-character.css';

const HANDLE_DRAG_THRESHOLD = 4;

export function PetWindow() {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [bubbleOpen, setBubbleOpen] = useState(true);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [lookDirection, setLookDirection] = useState<PetLookDirection | null>(null);
  const {
    connection, animation, bubbleText, sending, sendText, messages, clearSending,
    bones, feedCost, feeding, feedPet,
    confirmingTask, activeCheckIn, offerReview,
    selectCheckInTask, cancelCheckIn, startCheckIn, finishCheckInEarly,
    choosePlanOption, dismissPlanOptions, reselectPlanOptions, startReviewOffer, skipReviewOffer,
  } = usePetSocket();
  const rootRef = usePetWindowLayout(historyOpen);
  const { layerRef, boneCursorUrl } = useBoneCursor(true);
  const handleDrag = useRef<{
    id: number;
    lastX: number;
    lastY: number;
    startX: number;
    startY: number;
    active: boolean;
  } | null>(null);

  const openLibrary = () => window.desktop?.openChat('library');
  const openFullChat = () => window.desktop?.openChat('chat');
  const closePet = () => window.desktop?.closePet();
  const restartPet = () => window.desktop?.restartPet?.();
  const restartShortcut = window.desktop?.restartShortcut || 'Ctrl+Shift+R';
  const toggleHistory = () => setHistoryOpen((open) => !open);
  const todayPlan = () => {
    setBubbleOpen(true);
    sendText('今日计划');
  };
  const continueReview = () => {
    sendText('开始复习');
  };
  const startQuiz = () => {
    setBubbleOpen(true);
    sendText('今日小测');
  };
  const startWeakPoint = () => {
    setBubbleOpen(true);
    setActionsOpen(false);
    sendText('薄弱点回顾');
  };
  const focusAsk = () => {
    setComposerOpen(true);
    setBubbleOpen(true);
    window.setTimeout(() => {
      const box = rootRef.current?.querySelector('textarea');
      if (box instanceof HTMLTextAreaElement) {
        box.focus();
        window.desktop?.setPetClickThrough?.(false);
      }
    }, 40);
  };

  const latestAssistant = [...messages].reverse().find((line) => line.role === 'assistant');
  const latestUser = [...messages].reverse().find((line) => line.role === 'user');
  const waitingReview = latestAssistant?.metadata?.review;
  // Prefer the latest assistant turn so a fresh「三选一」isn't hidden by older task cards.
  const todayPlanCard = (
    latestAssistant?.metadata?.today_plan?.tasks?.length
      ? latestAssistant.metadata.today_plan
      : [...messages].reverse().find((line) => line.metadata?.today_plan?.tasks?.length)?.metadata?.today_plan
  );
  const planOptionsCard = (
    latestAssistant?.metadata?.plan_options?.length
      ? latestAssistant.metadata.plan_options
      : [...messages].reverse().find((line) => line.metadata?.plan_options?.length)?.metadata?.plan_options
  );
  const reviewWaiting = Boolean(
    waitingReview
    && (latestAssistant?.metadata?.mode === 'review_question'
      || latestAssistant?.metadata?.mode === 'review'
      || waitingReview.options?.length),
  ) && !messages.slice(messages.findIndex((m) => m.id === latestAssistant?.id) + 1).some((m) => m.role === 'user');

  const openTodayTasks = (todayPlanCard?.tasks || []).filter((task) => task.id && !task.done);
  const latestMode = latestAssistant?.metadata?.mode;
  const latestIsPlanUi = latestMode === 'today_plan'
    || latestMode === 'plan_options'
    || latestMode === 'check_in_started'
    || latestMode === 'task_reward';
  // Only keep plan checklist chrome while the latest turn is still about the plan.
  const showPlanChrome = Boolean(latestIsPlanUi || confirmingTask || activeCheckIn || offerReview);

  // New replies / questions reopen the bubble if the user had closed it.
  useEffect(() => {
    if (
      sending
      || animation === 'talking'
      || animation === 'thinking'
      || animation === 'searching'
      || animation === 'tool'
      || reviewWaiting
      || showPlanChrome
      || latestAssistant
    ) {
      setBubbleOpen(true);
    }
  }, [sending, animation, latestAssistant?.id, reviewWaiting, showPlanChrome]);

  const singleBubbleText = (() => {
    if (dragging) return '带我去那边～';
    if (animation === 'thinking' || animation === 'searching' || animation === 'tool') {
      return bubbleText || DEFAULT_BUBBLE_COPY[animation];
    }
    if (activeCheckIn) {
      return '打卡中～到点领骨头，提前说「我做完了」。';
    }
    if (offerReview && latestMode === 'task_reward') {
      return '骨头到手啦！要不要出一题巩固？';
    }
    if (confirmingTask && (latestIsPlanUi || !latestAssistant || latestMode === 'today_plan')) {
      return '确认内容后点「开始打卡」。';
    }
    if (reviewWaiting && latestAssistant) {
      // Prefer stem so A/B/C/D only appear as clickable buttons.
      const stem = waitingReview?.stem?.trim();
      if (stem && waitingReview?.options?.length) {
        const label =
          waitingReview.question_type === 'true_false' ? '判断'
            : waitingReview.question_type === 'multiple_choice' ? '单选'
              : '习题';
        return stem.startsWith('【') ? stem : `【${label}】${stem}`;
      }
      return latestAssistant.content;
    }
    // After a normal chat reply (e.g.「你好」), never keep covering it with plan chrome.
    if (latestAssistant?.content && !latestIsPlanUi) {
      return latestAssistant.content;
    }
    if (planOptionsCard?.length && latestMode === 'plan_options') {
      return '今日计划三选一：轻量 / 标准 / 加练';
    }
    if (animation === 'talking' && bubbleText) return bubbleText;
    if (openTodayTasks.length && latestMode === 'today_plan') {
      const day = todayPlanCard?.day;
      return day != null
        ? `📌 第 ${day} 天事办——选一项开始打卡`
        : '📌 今日事办——选一项开始打卡';
    }
    if (latestAssistant?.content) return latestAssistant.content;
    if (latestUser?.content) return `已收到：${latestUser.content.slice(0, 40)}${latestUser.content.length > 40 ? '…' : ''}`;
    return bubbleText || DEFAULT_BUBBLE_COPY.idle;
  })();

  function onHandlePointerDown(event: React.PointerEvent<HTMLSpanElement>) {
    if (event.button !== 0) return;
    handleDrag.current = {
      id: event.pointerId,
      lastX: event.screenX,
      lastY: event.screenY,
      startX: event.screenX,
      startY: event.screenY,
      active: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function onHandlePointerMove(event: React.PointerEvent<HTMLSpanElement>) {
    const track = handleDrag.current;
    if (!track || track.id !== event.pointerId) return;
    const totalX = event.screenX - track.startX;
    const totalY = event.screenY - track.startY;
    if (!track.active && Math.hypot(totalX, totalY) >= HANDLE_DRAG_THRESHOLD) {
      track.active = true;
      setDragging(true);
      setLookDirection(lookFromDelta(totalX, totalY) ?? 'right');
    }
    if (!track.active) return;
    const dx = event.screenX - track.lastX;
    const dy = event.screenY - track.lastY;
    if (Math.abs(dx) >= 1 || Math.abs(dy) >= 1) {
      window.desktop?.movePetBy?.(Math.round(dx), Math.round(dy));
      setLookDirection(lookFromDelta(totalX, totalY) ?? lookFromDelta(dx, dy));
      track.lastX = event.screenX;
      track.lastY = event.screenY;
    }
  }

  function onHandlePointerUp(event: React.PointerEvent<HTMLSpanElement>) {
    const track = handleDrag.current;
    if (!track || track.id !== event.pointerId) return;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* ignore */
    }
    handleDrag.current = null;
    if (track.active) {
      setDragging(false);
      setLookDirection(null);
    }
  }

  return (
    <div
      ref={rootRef}
      className={`pet-shell${historyOpen ? ' history-open' : ''}${dragging ? ' is-dragging' : ''}`}
      data-pet-shell
      data-state={animation}
      data-look={lookDirection || undefined}
    >
      <img
        ref={layerRef}
        className="pet-bone-cursor"
        src={boneCursorUrl}
        alt=""
        width={20}
        height={20}
        draggable={false}
      />
      <div className="pet-top" data-interactive>
        <span
          className="pet-handle"
          title="按住拖动桌宠"
          onPointerDown={onHandlePointerDown}
          onPointerMove={onHandlePointerMove}
          onPointerUp={onHandlePointerUp}
          onPointerCancel={onHandlePointerUp}
        >
          拖动
        </span>
        <button type="button" className="pet-close" aria-label="隐藏桌宠" onClick={closePet}>
          ×
        </button>
      </div>

      <div className="pet-stack">
        {bubbleOpen && historyOpen && (
          <PetHistoryStack messages={messages} currentText={singleBubbleText} />
        )}
        {bubbleOpen && (
          <PetBubble
            text={singleBubbleText}
            sending={sending}
            historyExpanded={historyOpen}
            options={reviewWaiting ? waitingReview?.options : undefined}
            tasks={!reviewWaiting && !activeCheckIn && !offerReview && latestMode === 'today_plan' ? todayPlanCard?.tasks : undefined}
            planOptions={!reviewWaiting && !activeCheckIn && !offerReview && !confirmingTask && latestMode === 'plan_options' ? planOptionsCard : undefined}
            confirmingTask={!reviewWaiting && showPlanChrome ? confirmingTask : null}
            activeFocus={!reviewWaiting ? activeCheckIn : null}
            offerReview={!reviewWaiting && offerReview && latestMode === 'task_reward'}
            onAnswer={(text) => sendText(text, { reviewAnswer: true })}
            onSelectTask={(task) => selectCheckInTask(task)}
            onChoosePlan={(option) => { void choosePlanOption(option); }}
            onDismissPlan={dismissPlanOptions}
            onReselectPlan={() => { reselectPlanOptions(); }}
            onStartCheckIn={() => { void startCheckIn(); }}
            onCancelCheckIn={cancelCheckIn}
            onFinishEarly={() => { void finishCheckInEarly(); }}
            onStartReview={() => { startReviewOffer(); }}
            onSkipReview={skipReviewOffer}
            onToggleHistory={toggleHistory}
            onOpenDesktopChat={openFullChat}
            onClose={() => {
              setBubbleOpen(false);
              setHistoryOpen(false);
            }}
          />
        )}
        <div className="pet-drag-zone" data-interactive title="按住小狗身体拖动；单击显示对话并输入">
          <PetCharacter
            state={animation}
            dragging={dragging}
            lookDirection={lookDirection}
            onBodyDrag={(active, direction) => {
              setDragging(active);
              setLookDirection(active ? direction : null);
            }}
            onClick={() => {
              setBubbleOpen(true);
              focusAsk();
            }}
            onDoubleClick={openFullChat}
          />
        </div>
        <div className="pet-dock" data-interactive>
          <button
            type="button"
            className={`pet-dock-btn${bubbleOpen ? ' is-on' : ''}`}
            title={bubbleOpen ? '收起对话框' : '显示对话框'}
            aria-pressed={bubbleOpen}
            onClick={() => {
              if (bubbleOpen) {
                setBubbleOpen(false);
                setHistoryOpen(false);
              } else {
                setBubbleOpen(true);
              }
            }}
          >
            {bubbleOpen ? '收起' : '对话'}
          </button>
          <button
            type="button"
            className={`pet-dock-btn${actionsOpen ? ' is-on' : ''}`}
            title={actionsOpen ? '收起菜单' : '展开菜单'}
            aria-expanded={actionsOpen}
            onClick={() => setActionsOpen((open) => !open)}
          >
            菜单
          </button>
          <button
            type="button"
            className={`pet-dock-btn${composerOpen ? ' is-on' : ''}`}
            title={composerOpen ? '收起输入框' : '展开输入框'}
            aria-expanded={composerOpen}
            onClick={() => {
              if (composerOpen) {
                setComposerOpen(false);
              } else {
                focusAsk();
              }
            }}
          >
            输入
          </button>
          <ConnectionStatus phase={connection} compact />
        </div>
        {actionsOpen && (
          <QuickActions
            chatOpen={historyOpen}
            onToggleChat={toggleHistory}
            onOpenLibrary={openLibrary}
            onAsk={focusAsk}
            onQuiz={startQuiz}
            onWeakPoint={startWeakPoint}
            onTodayPlan={todayPlan}
            onFeedPet={() => { void feedPet(); }}
            bones={bones}
            feedCost={feedCost}
            feeding={feeding}
          />
        )}
        {composerOpen && (
          <CompactChatInput
            connection={connection}
            sending={sending}
            onSend={(text) => {
              setBubbleOpen(true);
              return sendText(text);
            }}
            onCancelSending={clearSending}
            placeholder={
              reviewWaiting
                ? (waitingReview?.options?.length ? '点气泡选项，或输入简答…' : '在这里输入你的答案…')
                : '问资料问题，或按住麦克风说…'
            }
          />
        )}
      </div>

      <PetContextMenu
        chatOpen={historyOpen}
        restartShortcut={restartShortcut}
        onOpenChat={openFullChat}
        onOpenLibrary={openLibrary}
        onToggleChat={toggleHistory}
        onClosePet={closePet}
        onRestartPet={restartPet}
        onTodayPlan={todayPlan}
        onContinueReview={continueReview}
        onAsk={focusAsk}
        onQuiz={startQuiz}
        onWeakPoint={startWeakPoint}
        onFeedPet={() => { void feedPet(); }}
        feedLabel={feeding ? '喂食中…' : `喂骨头（${bones}/${feedCost}）`}
        feedDisabled={feeding || bones < feedCost}
      />
    </div>
  );
}
