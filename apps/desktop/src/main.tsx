import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { messageEvent, parseServerEvent } from './protocol';
import './style.css';

const endpoint = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/chat';
function App() {
  const socket = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState('连接中');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<string[]>([]);
  useEffect(() => {
    const ws = new WebSocket(endpoint); socket.current = ws;
    ws.onopen = () => setStatus('已连接');
    ws.onclose = () => setStatus('已断开：请启动后端并刷新');
    ws.onerror = () => setStatus('连接错误');
    ws.onmessage = (event) => { try { setMessages(old => [...old, `伙伴：${parseServerEvent(event.data).text}`]); } catch { setMessages(old => [...old, '收到无法解析的消息']); } };
    return () => { socket.current = null; ws.close(); };
  }, []);
  function send(e: React.FormEvent) {
    e.preventDefault(); const text = input.trim();
    if (!text || socket.current?.readyState !== WebSocket.OPEN) return;
    socket.current.send(messageEvent(text)); setMessages(old => [...old, `我：${text}`]); setInput('');
  }
  return <main><header><span className="pet" aria-label="桌宠占位形象">🐳</span><div><h1>AI 学习伙伴</h1><p>桌宠原型 · {status}</p></div></header><section aria-label="对话记录">{messages.map((message, i) => <p key={i}>{message}</p>)}</section><form onSubmit={send}><input aria-label="消息" value={input} onChange={e => setInput(e.target.value)} placeholder="说说你的学习计划…"/><button disabled={status !== '已连接'}>发送</button></form><footer>任务管理与角色动画将在后续迭代接入。</footer></main>;
}
createRoot(document.getElementById('root')!).render(<App />);
