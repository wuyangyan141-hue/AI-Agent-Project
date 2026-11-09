import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { messageEvent, parseServerEvent, type PetState } from './protocol';
import './style.css';
import './features.css';

type Task = { id: number; title: string; done: boolean; estimated_minutes: number; scheduled_day: number | null };
type PlanDraft = { id: number; steps?: { day: number; title: string; minutes: number }[]; schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[]; reason?: string };
type Review = { id: number; question: string; topic: string };
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
  const [goal, setGoal] = useState('');
  const [days, setDays] = useState(3);
  const [dailyMinutes, setDailyMinutes] = useState(45);
  const [draft, setDraft] = useState<PlanDraft | null>(null);
  const [draftKind, setDraftKind] = useState<'plan' | 'replan'>('plan');
  const [focus, setFocus] = useState<{ id: number | null; remaining_seconds: number; ends_at?: string }>({ id: null, remaining_seconds: 0 });
  const [focusMinutes, setFocusMinutes] = useState(25);
  const [reviewTopic, setReviewTopic] = useState('');
  const [review, setReview] = useState<Review | null>(null);
  const [reviewAnswer, setReviewAnswer] = useState('');
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [activity, setActivity] = useState('等待指令');

  async function loadTasks() {
    try { const response = await fetch(`${api}/tasks`); if (!response.ok) throw Error(); setTasks(await response.json()); }
    catch { setNotice('任务加载失败，请检查后端。'); }
  }
  useEffect(() => {
    loadTasks();
    fetch(`${api}/preferences/pet_name`).then(r => r.json()).then(v => setPetName(v.value)).catch(() => {});
    fetch(`${api}/focus`).then(r => r.json()).then(setFocus).catch(() => {});
    const ws = new WebSocket(endpoint); socket.current = ws;
    ws.onopen = () => setConnection('已连接');
    ws.onclose = () => { setConnection('已断开：请启动后端并刷新'); setPet('error'); };
    ws.onerror = () => setConnection('连接错误');
    ws.onmessage = event => {
      try {
        const data = parseServerEvent(event.data);
        setPet(data.state); setActivity(data.text); if (data.mode) setMode(data.mode);
        if (data.type !== 'status') setMessages(old => [...old, `${petName}：${data.text}`]);
      } catch { setNotice('收到无法解析的消息。'); }
    };
    return () => { socket.current = null; ws.close(); };
  }, []);
  useEffect(() => {
    if (!focus.id || !focus.ends_at) return;
    const update = () => setFocus(old => ({ ...old, remaining_seconds: Math.max(0, Math.ceil((Date.parse(old.ends_at!) - Date.now()) / 1000)) }));
    update(); const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [focus.id, focus.ends_at]);
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
  async function requestJson(path: string, method: string, body?: object) {
    const response = await fetch(`${api}${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw Error(data.detail || '请求失败'); }
    return response.json();
  }
  async function createDraft(kind: 'plan' | 'replan') {
    try {
      setPet('thinking'); setActivity('正在制定计划');
      const path = kind === 'plan' ? '/plans/drafts' : '/plans/replan-drafts';
      const result = await requestJson(path, 'POST', kind === 'plan' ? { goal, days, minutes_per_day: dailyMinutes } : { days, minutes_per_day: dailyMinutes });
      setDraft(result); setDraftKind(kind); setPet('success'); setActivity('计划草稿已生成，等待确认'); setNotice('请检查计划，确认后才会更新任务。');
    } catch (e) { setPet('error'); setNotice(String(e)); }
  }
  async function confirmDraft() {
    if (!draft) return;
    try {
      setPet('tool'); setActivity('正在保存计划');
      await requestJson(`/plans/${draftKind === 'plan' ? 'drafts' : 'replan-drafts'}/${draft.id}/confirm`, 'POST');
      setDraft(null); await loadTasks(); setPet('success'); setActivity('任务已更新'); setNotice('计划已保存。');
    } catch (e) { setPet('error'); setNotice(String(e)); }
  }
  async function editTask(task: Task) {
    const title = window.prompt('修改任务名称', task.title); if (title === null) return;
    const minutes = Number(window.prompt('预计分钟数', String(task.estimated_minutes)));
    if (!title.trim() || !Number.isInteger(minutes) || minutes < 5 || minutes > 240) { setNotice('请输入任务名称和 5–240 分钟的时长。'); return; }
    try { await requestJson(`/tasks/${task.id}`, 'PATCH', { title: title.trim(), estimated_minutes: minutes }); await loadTasks(); }
    catch (e) { setNotice(String(e)); }
  }
  async function startFocus() {
    try { setFocus(await requestJson('/focus', 'POST', { minutes: focusMinutes })); setPet('tool'); setActivity('专注计时已开始'); }
    catch (e) { setNotice(String(e)); }
  }
  async function stopFocus() {
    if (!focus.id) return;
    try { await requestJson(`/focus/${focus.id}/finish`, 'POST'); setFocus({ id: null, remaining_seconds: 0 }); setPet('success'); setActivity('专注已结束'); }
    catch (e) { setNotice(String(e)); }
  }
  async function startReview() {
    try { const result = await requestJson('/reviews', 'POST', { topic: reviewTopic }); setReview(result); setReviewFeedback(''); setPet('thinking'); setActivity('等待回答'); }
    catch (e) { setNotice(String(e)); }
  }
  async function submitReview() {
    if (!review) return;
    try { const result = await requestJson(`/reviews/${review.id}/answer`, 'POST', { answer: reviewAnswer }); setReviewFeedback(result.feedback); setReview(null); setReviewAnswer(''); setPet('success'); setActivity('复习反馈已生成'); }
    catch (e) { setNotice(String(e)); }
  }
  return <main>
    <header><span className={`pet ${pet}`} role="img" aria-label={`${petName}${labels[pet]}`}>🐳</span><div><h1>{petName} · AI 学习伙伴</h1><p>{connection} · {labels[pet]} · {mode === 'demo' ? '演示模式' : 'LangChain 模式'}</p><small>{activity}</small></div></header>
    <nav aria-label="功能"><button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>聊天</button><button className={tab === 'tasks' ? 'active' : ''} onClick={() => { setTab('tasks'); loadTasks(); }}>任务</button><button className={tab === 'settings' ? 'active' : ''} onClick={() => setTab('settings')}>设置</button></nav>
    {tab === 'chat' && <><section aria-label="对话记录">{messages.map((message, i) => <p key={i}>{message}</p>)}</section><form onSubmit={send}><input aria-label="消息" value={input} onChange={e => setInput(e.target.value)} placeholder="说说你的学习计划…" maxLength={4000}/><button disabled={connection !== '已连接'}>发送</button></form></>}
    {tab === 'tasks' && <section><h2>学习计划</h2><div className="controls"><input aria-label="学习目标" value={goal} onChange={e => setGoal(e.target.value)} placeholder="例如：复习数据库索引"/><label>天数<input aria-label="计划天数" type="number" min={1} max={14} value={days} onChange={e => setDays(Number(e.target.value))}/></label><label>每天分钟<input aria-label="每日分钟" type="number" min={15} max={240} value={dailyMinutes} onChange={e => setDailyMinutes(Number(e.target.value))}/></label></div><div className="controls"><button onClick={() => createDraft('plan')} disabled={!goal.trim()}>生成新计划</button><button onClick={() => createDraft('replan')}>重新安排未完成任务</button></div>{draft && <div className="draft"><h3>计划草稿（尚未保存）</h3><p>{draft.reason}</p><ol>{(draft.steps || draft.schedule || []).map((step, i) => <li key={i}>第 {step.day} 天 · {step.title} · {step.minutes} 分钟</li>)}</ol><button onClick={confirmDraft}>确认并保存</button><button onClick={() => setDraft(null)}>取消</button></div>}<h2>学习任务</h2><form onSubmit={addTask}><input aria-label="新任务" value={taskTitle} onChange={e => setTaskTitle(e.target.value)} placeholder="例如：复习数据库索引" maxLength={200}/><button>添加</button></form><ul>{tasks.map(task => <li key={task.id}><label><input type="checkbox" checked={task.done} onChange={() => toggleTask(task)}/><span className={task.done ? 'done' : ''}>{task.title} · {task.estimated_minutes} 分钟{task.scheduled_day ? ` · 第 ${task.scheduled_day} 天` : ''}</span></label><button onClick={() => editTask(task)}>修改</button></li>)}</ul><h2>专注计时</h2>{focus.id ? <div><strong>{Math.floor(focus.remaining_seconds / 60)}:{String(focus.remaining_seconds % 60).padStart(2, '0')}</strong><button onClick={stopFocus}>结束</button></div> : <div className="controls"><input aria-label="专注分钟" type="number" min={1} max={240} value={focusMinutes} onChange={e => setFocusMinutes(Number(e.target.value))}/><button onClick={startFocus}>开始专注</button></div>}<h2>交互式复习</h2><div className="controls"><input aria-label="复习知识点" value={reviewTopic} onChange={e => setReviewTopic(e.target.value)} placeholder="例如：B+树"/><button onClick={startReview} disabled={!reviewTopic.trim()}>开始复习</button></div>{review && <div><p>{review.question}</p><textarea aria-label="我的回答" value={reviewAnswer} onChange={e => setReviewAnswer(e.target.value)}/><button onClick={submitReview} disabled={!reviewAnswer.trim()}>提交回答</button></div>}{reviewFeedback && <p role="status">{reviewFeedback}</p>}</section>}
    {tab === 'settings' && <section><h2>设置</h2><form onSubmit={saveName}><label htmlFor="pet-name">桌宠名字</label><input id="pet-name" value={petName} onChange={e => setPetName(e.target.value)} maxLength={100}/><button>保存</button></form><p>当前模式：{mode === 'demo' ? '演示回复（未配置模型密钥）' : 'LangChain Agent'}</p></section>}
    <footer role="status">{notice || '桌宠会根据后端事件切换状态。'}</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
