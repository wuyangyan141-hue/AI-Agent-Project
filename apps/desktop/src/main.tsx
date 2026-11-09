import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { messageEvent, parseServerEvent, type PetState } from './protocol';
import './style.css';

type Task = { id: number; title: string; done: boolean };
const endpoint = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/chat';
const api = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const labels: Record<PetState, string> = { idle: '准备好了', thinking: '正在思考', searching: '正在检索', tool: '正在调用工具', success: '完成啦', error: '遇到问题' };

function App() {
  const socket = useRef<WebSocket | null>(null);
  const [tab, setTab] = useState<'chat' | 'tasks' | 'settings'>('chat');
  const [connection, setConnection] = useState('连接中');
  const [mode, setMode] = useState('demo');
  const [pet, setPet] = useState<PetState>('idle');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<string[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskTitle, setTaskTitle] = useState('');
  const [petName, setPetName] = useState('小鲸');
  const [notice, setNotice] = useState('');

  async function loadTasks() {
    try { const response = await fetch(`${api}/tasks`); if (!response.ok) throw Error(); setTasks(await response.json()); }
    catch { setNotice('任务加载失败，请检查后端。'); }
  }
  useEffect(() => {
    loadTasks();
    fetch(`${api}/preferences/pet_name`).then(r => r.json()).then(v => setPetName(v.value)).catch(() => {});
    const ws = new WebSocket(endpoint); socket.current = ws;
    ws.onopen = () => setConnection('已连接');
    ws.onclose = () => { setConnection('已断开：请启动后端并刷新'); setPet('error'); };
    ws.onerror = () => setConnection('连接错误');
    ws.onmessage = event => {
      try {
        const data = parseServerEvent(event.data);
        setPet(data.state); if (data.mode) setMode(data.mode);
        if (data.type !== 'status') setMessages(old => [...old, `${petName}：${data.text}`]);
      } catch { setNotice('收到无法解析的消息。'); }
    };
    return () => { socket.current = null; ws.close(); };
  }, []);
  function send(e: React.FormEvent) {
    e.preventDefault(); const text = input.trim();
    if (!text || socket.current?.readyState !== WebSocket.OPEN) return;
    socket.current.send(messageEvent(text)); setMessages(old => [...old, `我：${text}`]); setInput('');
  }
  async function addTask(e: React.FormEvent) {
    e.preventDefault(); if (!taskTitle.trim()) return;
    try {
      const r = await fetch(`${api}/tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: taskTitle.trim() }) });
      if (!r.ok) throw Error(); setTaskTitle(''); await loadTasks(); setNotice('任务已添加。');
    } catch { setNotice('添加失败，请检查后端。'); }
  }
  async function toggleTask(task: Task) {
    try {
      const r = await fetch(`${api}/tasks/${task.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ done: !task.done }) });
      if (!r.ok) throw Error(); await loadTasks();
    } catch { setNotice('更新失败。'); }
  }
  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await fetch(`${api}/preferences/pet_name`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: petName }) });
      if (!r.ok) throw Error(); setNotice('设置已保存。');
    } catch { setNotice('保存失败。'); }
  }
  return <main>
    <header><span className={`pet ${pet}`} role="img" aria-label={`${petName}${labels[pet]}`}>🐳</span><div><h1>{petName} · AI 学习伙伴</h1><p>{connection} · {labels[pet]} · {mode === 'demo' ? '演示模式' : 'LangChain 模式'}</p></div></header>
    <nav aria-label="功能"><button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>聊天</button><button className={tab === 'tasks' ? 'active' : ''} onClick={() => { setTab('tasks'); loadTasks(); }}>任务</button><button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>设置</button></nav>
    {tab === 'chat' && <><section aria-label="对话记录">{messages.map((message, i) => <p key={i}>{message}</p>)}</section><form onSubmit={send}><input aria-label="消息" value={input} onChange={e => setInput(e.target.value)} placeholder="说说你的学习计划…" maxLength={4000}/><button disabled={connection !== '已连接'}>发送</button></form></>}
    {tab === 'tasks' && <section><h2>学习任务</h2><form onSubmit={addTask}><input aria-label="新任务" value={taskTitle} onChange={e => setTaskTitle(e.target.value)} placeholder="例如：复习数据库索引" maxLength={200}/><button>添加</button></form><ul>{tasks.map(task => <li key={task.id}><label><input type="checkbox" checked={task.done} onChange={() => toggleTask(task)}/><span className={task.done ? 'done' : ''}>{task.title}</span></label></li>)}</ul></section>}
    {tab === 'settings' && <section><h2>设置</h2><form onSubmit={saveName}><label htmlFor="pet-name">桌宠名字</label><input id="pet-name" value={petName} onChange={e => setPetName(e.target.value)} maxLength={100}/><button>保存</button></form><p>当前模式：{mode === 'demo' ? '演示回复（未配置模型密钥）' : 'LangChain Agent'}</p></section>}
    <footer role="status">{notice || '桌宠会根据后端事件切换状态。'}</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
