import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { parseServerEvent, type PetState } from './protocol';
import './pet.css';

declare global {
  interface Window { desktop?: { platform: string; openChat(): void; showPet(): void; closePet(): void } }
}

const status: Record<PetState, string> = {
  idle: '准备学习', thinking: '正在思考', searching: '正在检索',
  tool: '正在执行', success: '完成啦', error: '遇到问题',
};

function PetWindow() {
  const [state, setState] = useState<PetState>('idle');
  const [caption, setCaption] = useState(status.idle);
  useEffect(() => {
    const channel = new BroadcastChannel('learning-companion-pet');
    channel.onmessage = event => {
      try {
        const update = parseServerEvent(JSON.stringify(event.data));
        setState(update.state);
        setCaption(update.text.slice(0, 60) || status[update.state]);
      } catch { /* Ignore unrelated channel messages. */ }
    };
    return () => channel.close();
  }, []);
  return <div className="pet-window">
    <div className="pet-handle" title="按住这里拖动桌宠" aria-label="拖动桌宠">⋮⋮</div>
    <button className="pet-close" aria-label="关闭桌宠" onClick={() => window.desktop?.closePet()}>×</button>
    <button className={`pet-character ${state}`} aria-label={`打开聊天，${status[state]}`} onClick={() => window.desktop?.openChat()} title="点击打开聊天">🐳</button>
    <div className="pet-bubble" role="status">{caption}</div>
  </div>;
}

createRoot(document.getElementById('root')!).render(<PetWindow />);
