import React, { useRef, useState } from 'react';
import { lookFromDelta, type PetLookDirection } from './animationAssets';
import { CompactChatInput } from './CompactChatInput';
import { ConnectionStatus } from './ConnectionStatus';
import { PetBubble } from './PetBubble';
import { PetCharacter } from './PetCharacter';
import { PetChatLog } from './PetChatLog';
import { PetContextMenu } from './PetContextMenu';
import { QuickActions } from './QuickActions';
import { useBoneCursor } from './useBoneCursor';
import { usePetSocket } from './usePetSocket';
import { usePetWindowLayout } from './usePetWindow';
import { DEFAULT_BUBBLE_COPY } from './types';
import './pet-window.css';
import './pet-character.css';

const HANDLE_DRAG_THRESHOLD = 4;

export function PetWindow() {
  const [chatOpen, setChatOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [lookDirection, setLookDirection] = useState<PetLookDirection | null>(null);
  const { connection, animation, bubbleText, sending, sendText, messages, clearSending } = usePetSocket();
  const rootRef = usePetWindowLayout(chatOpen);
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
  const toggleChat = () => setChatOpen((open) => !open);
  const openChatPanel = () => setChatOpen(true);
  const todayPlan = () => {
    setChatOpen(true);
    sendText('下一步');
  };
  const continueReview = () => {
    setChatOpen(true);
    sendText('开始复习');
  };

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
      // Prefer total drag direction so gaze stays with the pull, not micro jitters.
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
      className={`pet-shell${chatOpen ? ' chat-open' : ''}${dragging ? ' is-dragging' : ''}`}
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
        {chatOpen ? (
          <PetChatLog
            messages={messages}
            liveText={
              dragging
                ? '带我去那边～'
                : animation === 'thinking' || animation === 'searching' || animation === 'tool' || animation === 'talking'
                  ? bubbleText
                  : undefined
            }
            onOpenFullChat={openFullChat}
          />
        ) : (
          <PetBubble
            text={dragging ? '带我去那边～' : DEFAULT_BUBBLE_COPY.idle}
            onOpenFullChat={openChatPanel}
          />
        )}
        <div className="pet-drag-zone" data-interactive title="按住小狗身体拖动；单击挥手开聊天">
          <PetCharacter
            state={animation}
            dragging={dragging}
            lookDirection={lookDirection}
            onBodyDrag={(active, direction) => {
              setDragging(active);
              setLookDirection(active ? direction : null);
            }}
            onClick={chatOpen ? toggleChat : openChatPanel}
            onDoubleClick={openFullChat}
          />
        </div>
        <QuickActions chatOpen={chatOpen} onToggleChat={toggleChat} onOpenLibrary={openLibrary} />
        {chatOpen && (
          <>
            <ConnectionStatus phase={connection} />
            <CompactChatInput
              connection={connection}
              sending={sending}
              onSend={sendText}
              onCancelSending={clearSending}
            />
          </>
        )}
      </div>

      <PetContextMenu
        chatOpen={chatOpen}
        restartShortcut={restartShortcut}
        onOpenChat={openFullChat}
        onOpenLibrary={openLibrary}
        onToggleChat={toggleChat}
        onClosePet={closePet}
        onRestartPet={restartPet}
        onTodayPlan={todayPlan}
        onContinueReview={continueReview}
      />
    </div>
  );
}
