import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { messageEvent, parseServerEvent, type PetState } from './protocol';
import { DogAvatar } from './DogAvatar';
import { KnowledgePanels } from './KnowledgePanels';
import { api,request,sourcePosition,type ChatMessage,type Source,type KnowledgeDocument,type LearningNextStep,type ReviewChoice } from './knowledge';
import type { PanelTab } from './desktop';
import './desktop';
import { conversation, useConversation, scopeFields } from './chatStore';
import './style.css';
import './features.css';

type Task = { id: number; title: string; done: boolean; estimated_minutes: number; scheduled_day: number | null; deleted_at?: string | null; bones_awarded?: boolean; reward?: { bones_earned?: number; bones?: number; message?: string; streak?: StreakInfo } };
type StreakInfo = { current_streak?: number; achievements?: string[]; achievement_labels?: string[]; total_focus_minutes?: number; bones?: number; tasks_completed?: number; feed_cost?: number; pet_feeds?: number };
type PlanDraft = { id: number; steps?: { day: number; title: string; minutes: number }[]; schedule?: { day: number; title: string; minutes: number; previous_day: number | null }[]; reason?: string };
type Review = { id: number; question: string; topic: string; question_type?: string; options?: ReviewChoice[]; stem?: string };
const endpoint = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/chat';
const labels: Record<PetState, string> = { idle: '准备好了', thinking: '正在思考', searching: '正在检索', tool: '正在调用工具', talking: '正在回答', success: '完成啦', error: '遇到问题' };

function App() {
  const socket = useRef<WebSocket | null>(null);
  const [tab, setTab] = useState<PanelTab>((['chat','tasks','library','memory','history','settings'].includes(location.hash.slice(1))?location.hash.slice(1):'library') as PanelTab);
  const [connection, setConnection] = useState('连接中');
  const [mode, setMode] = useState('demo');
  const [pet, setPet] = useState<PetState>('idle');
  const [input, setInput] = useState('');
  const shared = useConversation();
  const messages = shared.messages;
  const setMessages = conversation.setMessages;
  const [sending,setSending]=useState(false);
  const [documents,setDocuments]=useState<KnowledgeDocument[]>([]);
  const scope=shared.scope;
  const setScope=(scope:string)=>conversation.update({scope});
  const [source,setSource]=useState<Source|null>(null);
  const [documentVersion,setDocumentVersion]=useState(0);
  const session=useRef<string|null>(shared.sessionId);
  session.current=shared.sessionId;
  const channel=useRef<BroadcastChannel|null>(null);
  const messagesEnd=useRef<HTMLDivElement>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [trash, setTrash] = useState<Task[]>([]);
  const [showTrash, setShowTrash] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [petName, setPetName] = useState('豆豆');
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
  const [nextStep, setNextStep] = useState<LearningNextStep | null>(null);
  const [streak, setStreak] = useState<StreakInfo | null>(null);
  type LlmPreset = { id: string; label: string; base_url: string; model: string };
  type LlmSettings = {
    mode: 'offline' | 'online';
    provider: string;
    llm_model: string;
    llm_base_url: string;
    llm_api_key: string;
    has_api_key?: boolean;
    api_key_masked?: string;
    online_ready?: boolean;
    agent_mode?: string;
    presets?: LlmPreset[];
    hint?: string;
  };
  const [llm, setLlm] = useState<LlmSettings>({
    mode: 'offline', provider: 'custom', llm_model: '', llm_base_url: '', llm_api_key: '', presets: [],
  });
  const [llmBusy, setLlmBusy] = useState(false);

  async function loadTasks() {
    try {
      const [active, trashed] = await Promise.all([
        fetch(`${api}/tasks`).then(r => { if (!r.ok) throw Error(); return r.json(); }),
        fetch(`${api}/tasks/trash`).then(r => { if (!r.ok) throw Error(); return r.json(); }),
      ]);
      setTasks(active);
      setTrash(trashed);
    } catch { setNotice('任务加载失败，请检查后端。'); }
  }
  useEffect(()=>{ setSending(Boolean(shared.pending)); },[shared.pending]);
  useEffect(()=>{if(shared.status){setPet(shared.status.state);setActivity(shared.status.text);}},[shared.status?.state,shared.status?.text]);
  useEffect(()=>{ if(shared.openCitation){setSource(shared.openCitation.source);setTab('chat');} },[shared.openCitation?.token]);
  useEffect(()=>{
    const latest=[...messages].reverse().find(m=>m.role==='assistant');
    if(latest?.metadata?.draft){setDraft(latest.metadata.draft);setDraftKind(latest.metadata.kind||'plan');}
    if(latest?.metadata?.next_step)setNextStep(latest.metadata.next_step);
  },[messages]);
  useEffect(() => {
    loadTasks();
    fetch(`${api}/preferences/pet_name`).then(r => r.json()).then(v => setPetName(v.value)).catch(() => {});
    fetch(`${api}/focus`).then(r => r.json()).then(setFocus).catch(() => {});
    fetch(`${api}/learning/streak`).then(r => r.json()).then(setStreak).catch(() => {});
    fetch(`${api}/learning/next-step`).then(r => r.json()).then(setNextStep).catch(() => {});
    let closed = false;
    let retry = 0;
    let retryTimer: number | null = null;
    const petChannel = new BroadcastChannel('learning-companion-pet');

    channel.current=petChannel;

    const attachSocket = () => {
      if (closed) return;
      setConnection(retry === 0 ? '连接中' : `重连中（第 ${retry} 次）…`);
      const ws = new WebSocket(endpoint);
      socket.current = ws;
      ws.onopen = () => {
        retry = 0;
        setConnection('已连接');
        setPet('idle');
      };
      ws.onclose = () => {
        if (socket.current === ws) socket.current = null;
        setSending(false);
        if (closed) return;
        setPet('error');
        retry += 1;
        const wait = Math.min(8000, 800 * retry);
        setConnection(`已断开：正在重连（${Math.round(wait / 1000)}s）…`);
        retryTimer = window.setTimeout(attachSocket, wait);
      };
      ws.onerror = () => setConnection('连接错误，稍后自动重试');
      ws.onmessage = event => {
        try {
          const data = parseServerEvent(event.data);
          if (data.mode) setMode(data.mode);
          if (data.type === 'welcome') {
            // Keep the pet bubble short — never mirror the full welcome essay.
            setPet('idle');
            setActivity(data.next_step?.title || '今天想学习什么？');
            if (data.next_step) setNextStep(data.next_step as LearningNextStep);
            return;
          }
          setPet(data.state); setActivity(data.text);
          if(!conversation.receive(data))return;
          if(data.type==='plan_draft'&&data.draft){setDraft(data.draft);setDraftKind(data.kind||'plan');}
          if(data.next_step)setNextStep(data.next_step as LearningNextStep);
        } catch { setNotice('收到无法解析的消息。'); }
      };
    };
    attachSocket();
    const unsubscribe=window.desktop?.onNavigate(setTab);
    return () => {
      closed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      unsubscribe?.();
      socket.current?.close();
      socket.current = null;
      petChannel.close();

      channel.current=null;
    };
  }, []);
  useEffect(() => {
    // Light reminder around preferred study window (local preference study_time like 20:00–21:00).
    const timer = window.setInterval(async () => {
      try {
        const prefs = await request<Record<string, string>>('/knowledge/preferences');
        const windowText = prefs.study_time || '';
        const match = windowText.match(/(\d{1,2}):(\d{2})/);
        if (!match) return;
        const now = new Date();
        const targetH = Number(match[1]);
        const targetM = Number(match[2]);
        if (now.getHours() === targetH && now.getMinutes() === targetM) {
          const step = await request<LearningNextStep>('/learning/next-step');
          setNextStep(step);
          setNotice(`到点啦：${step.suggestion}`);
          setPet('idle');
          setActivity(step.title);
        }
      } catch { /* ignore */ }
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(()=>{request<KnowledgeDocument[]>('/knowledge/documents').then(setDocuments).catch(()=>{});},[documentVersion,tab]);
  useEffect(()=>{if(!['auto','all','chat','selection'].includes(scope)&&!documents.some(d=>d.id===scope&&d.status==='ready'&&!d.needs_reindex))setScope('auto');},[documents]);
  useEffect(()=>{const event={type:'status',state:pet,text:activity};if(window.desktop)window.desktop.publishState(event);else channel.current?.postMessage(event);},[pet,activity]);
  useEffect(()=>{messagesEnd.current?.scrollIntoView({behavior:'smooth'});},[messages,sending]);
  useEffect(()=>{const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')setSource(null);};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[]);
  const focusAutoFinished = useRef<number | null>(null);
  useEffect(() => {
    if (!focus.id || !focus.ends_at) return;
    const update = () => setFocus(old => ({ ...old, remaining_seconds: Math.max(0, Math.ceil((Date.parse(old.ends_at!) - Date.now()) / 1000)) }));
    update(); const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [focus.id, focus.ends_at]);
  useEffect(() => {
    if (!focus.id || focus.remaining_seconds > 0) return;
    if (focusAutoFinished.current === focus.id) return;
    const sessionId = focus.id;
    focusAutoFinished.current = sessionId;
    void (async () => {
      const text = '时间到～';
      try {
        const result = await requestJson(`/focus/${sessionId}/finish`, 'POST');
        setFocus({ id: null, remaining_seconds: 0 });
        setPet('success');
        setActivity(text);
        if (result.streak) setStreak(result.streak);
        if (result.next_step) setNextStep(result.next_step);
        setNotice(result.streak?.current_streak ? `时间到！连续学习 ${result.streak.current_streak} 天` : text);
      } catch {
        setFocus({ id: null, remaining_seconds: 0 });
        setPet('success');
        setActivity(text);
        setNotice(text);
      }
    })();
  }, [focus.id, focus.remaining_seconds]);
  function sendText(text:string,documentId?:string,forceKnowledge=false){
    if(!text.trim() || sending || socket.current?.readyState!==WebSocket.OPEN)return;
    const chosen=documentId||scope;
    const requestId=conversation.begin(text.trim(),chosen);
    if(!requestId)return;
    socket.current.send(JSON.stringify({...JSON.parse(messageEvent(text.trim())),session_id:session.current,request_id:requestId,
      ...scopeFields(chosen),knowledge:forceKnowledge||scopeFields(chosen).knowledge}));
    setInput('');
  }
  function send(e: React.FormEvent) {
    e.preventDefault();sendText(input);
  }
  function openConversation(id:string,items:ChatMessage[]){
    if(sending){setNotice('等豆豆完成当前回答后，再打开历史对话。');return;}
    request<{document_ids:string[]|null}>(`/knowledge/sessions/${id}/context`).then(ctx=>{conversation.open(id,items,ctx.document_ids?.length===1?ctx.document_ids[0]:ctx.document_ids&&ctx.document_ids.length>1?'selection':'auto',ctx.document_ids||[]);setDraft(null);setTab('chat');setSource(null);}).catch(e=>setNotice(String(e)));
  }
  function askKnowledge(text:string,documentId?:string){
    setTab('chat');setScope(documentId||'all');if(text)sendText(text,documentId||'all',true);
  }
  function newChat(){
    if(sending)return;conversation.newChat();setDraft(null);setSource(null);setTab('chat');setInput('');
  }
  function planFromChat() {
    const text = input.trim();
    if (!text || text.length > 200 || sending || socket.current?.readyState !== WebSocket.OPEN) return;
    const requestId=conversation.begin(`请为「${text}」制定 ${days} 天计划，每天 ${dailyMinutes} 分钟`);
    if(!requestId)return;
    socket.current.send(JSON.stringify({type:'plan_request',session_id:session.current,request_id:requestId,...scopeFields(scope),payload:{goal:text,days,minutes_per_day:dailyMinutes}}));
    setInput('');
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
      const updated = await requestJson(`/tasks/${task.id}`, 'PATCH', { done: !task.done }) as Task;
      await loadTasks();
      if (updated.reward) {
        if (updated.reward.streak) setStreak(updated.reward.streak);
        setPet('success');
        setActivity(updated.reward.message || '任务完成');
        setNotice(updated.reward.message || `完成任务！获得 ${updated.reward.bones_earned || 1} 根骨头`);
      }
    } catch { setNotice('更新失败。'); }
  }
  async function deleteTask(task: Task) {
    if (!confirm(`把「${task.title}」移到回收站？之后还能恢复。`)) return;
    try {
      await requestJson(`/tasks/${task.id}`, 'DELETE');
      await loadTasks();
      setNotice('已移到回收站。');
    } catch (e) { setNotice(String(e)); }
  }
  async function restoreTask(task: Task) {
    try {
      await requestJson(`/tasks/${task.id}/restore`, 'POST');
      await loadTasks();
      setNotice('任务已恢复。');
    } catch (e) { setNotice(String(e)); }
  }
  async function purgeTask(task: Task) {
    if (!confirm(`永久删除「${task.title}」？此操作无法撤销。`)) return;
    try {
      await requestJson(`/tasks/${task.id}/purge`, 'DELETE');
      await loadTasks();
      setNotice('已永久删除。');
    } catch (e) { setNotice(String(e)); }
  }
  async function feedPetWithBones() {
    const cost = streak?.feed_cost || 3;
    if ((streak?.bones || 0) < cost) {
      setNotice(`骨头不够：喂豆豆需要 ${cost} 根。先完成学习任务攒骨头吧。`);
      return;
    }
    try {
      const result = await requestJson('/learning/bones/feed', 'POST') as { message?: string; speech?: string; streak?: StreakInfo };
      if (result.streak) setStreak(result.streak);
      const speech = (result.speech || result.message || '汪！好吃～').trim();
      // Talking bubble for the floating pet; full detail stays in the footer notice.
      setPet('talking');
      setActivity(speech);
      setNotice(result.message || speech);
      conversation.setMessages(msgs => [...msgs, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: speech,
        metadata: { mode: 'pet_feed' },
      }]);
      conversation.update({ status: { state: 'talking', text: speech } });
      window.desktop?.showPet?.();
    } catch (e) { setNotice(String(e)); }
  }
  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await fetch(`${api}/preferences/pet_name`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value: petName }) });
      if (!r.ok) throw Error(); setNotice('设置已保存。');
    } catch { setNotice('保存失败。'); }
  }
  async function loadLlmSettings() {
    try {
      const data = await requestJson('/settings/llm', 'GET') as LlmSettings;
      setLlm({
        mode: data.mode || 'offline',
        provider: data.provider || 'custom',
        llm_model: data.llm_model || '',
        llm_base_url: data.llm_base_url || '',
        llm_api_key: '',
        has_api_key: data.has_api_key,
        api_key_masked: data.api_key_masked,
        online_ready: data.online_ready,
        agent_mode: data.agent_mode,
        presets: data.presets || [],
        hint: data.hint,
      });
      if (data.agent_mode) setMode(data.agent_mode);
    } catch { /* keep current */ }
  }
  async function saveLlmSettings(e: React.FormEvent) {
    e.preventDefault();
    setLlmBusy(true);
    try {
      const body: Record<string, string> = {
        mode: llm.mode,
        provider: llm.provider,
        llm_model: llm.llm_model.trim(),
        llm_base_url: llm.llm_base_url.trim(),
      };
      if (llm.llm_api_key.trim()) body.llm_api_key = llm.llm_api_key.trim();
      const data = await requestJson('/settings/llm', 'PUT', body) as LlmSettings;
      setLlm((prev) => ({
        ...prev,
        mode: data.mode,
        provider: data.provider,
        llm_model: data.llm_model,
        llm_base_url: data.llm_base_url,
        llm_api_key: '',
        has_api_key: data.has_api_key,
        api_key_masked: data.api_key_masked,
        online_ready: data.online_ready,
        agent_mode: data.agent_mode,
        presets: data.presets || prev.presets,
        hint: data.hint,
      }));
      if (data.agent_mode) setMode(data.agent_mode);
      setNotice(data.mode === 'online' ? (data.online_ready ? '已切换为在线模式，复习批改会走你的 API。' : '在线配置不完整。') : '已切换为离线模式。');
    } catch (err) {
      setNotice(String(err));
    } finally {
      setLlmBusy(false);
    }
  }
  function applyPreset(id: string) {
    const preset = (llm.presets || []).find((item) => item.id === id);
    if (!preset) { setLlm((prev) => ({ ...prev, provider: id })); return; }
    setLlm((prev) => ({
      ...prev,
      provider: preset.id,
      llm_base_url: preset.base_url || prev.llm_base_url,
      llm_model: preset.model || prev.llm_model,
    }));
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
      const result = await requestJson(path, 'POST', kind === 'plan' ? { goal, days, minutes_per_day: dailyMinutes,session_id:session.current,...scopeFields(scope) } : { days, minutes_per_day: dailyMinutes });
      setDraft(result); setDraftKind(kind); setPet('success'); setActivity('计划草稿已生成，等待确认'); setNotice('请检查计划，确认后才会更新任务。');
    } catch (e) { setPet('error'); setNotice(String(e)); }
  }
  async function confirmDraft() {
    if (!draft) return;
    try {
      setPet('tool'); setActivity('正在保存计划');
      await requestJson(`/plans/${draftKind === 'plan' ? 'drafts' : 'replan-drafts'}/${draft.id}/confirm`, 'POST');
      setDraft(null); await loadTasks(); setPet('success'); setActivity('任务已更新'); setNotice('计划已保存。桌宠会提醒你开始专注～');
      const step = await request<LearningNextStep>('/learning/next-step?after=plan');
      setNextStep(step);
    } catch (e) { setPet('error'); setNotice(String(e)); }
  }
  async function bookmarkSource() {
    if (!source) return;
    try {
      await request('/knowledge/bookmarks', { method: 'POST', body: JSON.stringify({ document_id: source.document_id, chunk_id: source.chunk_id, note: '重点收藏' }) });
      setNotice('已收藏到知识库。');
    } catch (e) { setNotice(String(e)); }
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
    try {
      const result = await requestJson(`/focus/${focus.id}/finish`, 'POST');
      setFocus({ id: null, remaining_seconds: 0 });
      setPet('success'); setActivity('专注已结束');
      if (result.streak) setStreak(result.streak);
      if (result.next_step) setNextStep(result.next_step);
      setNotice(result.streak?.current_streak ? `专注完成！连续学习 ${result.streak.current_streak} 天` : '专注完成，来做一题复习吧。');
    }
    catch (e) { setNotice(String(e)); }
  }
  async function startReview() {
    try { const result = await requestJson('/reviews', 'POST', {topic:reviewTopic,session_id:session.current,...scopeFields(scope)}); setReview(result); setReviewFeedback(''); setPet('thinking'); setActivity('等待回答'); }
    catch (e) { setNotice(String(e)); }
  }
  async function submitReview(answer = reviewAnswer) {
    if (!review || !answer.trim()) return;
    try { const result = await requestJson(`/reviews/${review.id}/answer`, 'POST', { answer: answer.trim() }); setReviewFeedback(result.feedback); setReview(null); setReviewAnswer(''); setPet('success'); setActivity('复习反馈已生成'); }
    catch (e) { setNotice(String(e)); }
  }
  async function pickReviewOption(option: ReviewChoice) {
    setReviewAnswer(option.key);
    await submitReview(option.key);
  }
  return <main className="companion-panel">
    <header className="app-header"><button className="header-dog" title="显示桌面小狗" aria-label="显示桌面小狗" onClick={()=>window.desktop?.showPet()}><DogAvatar state={pet}/></button><div><span className="overline">YOUR LITTLE STUDY COMPANION</span><h1>{petName}<span> · 陪你学一点</span></h1><p><span className={`connection-dot ${connection==='已连接'?'online':''}`}/>{connection} · {labels[pet]} · {mode==='demo'?'本地离线模式':'模型已配置'}</p></div><div className="header-actions"><button className="quiet" disabled={sending} onClick={newChat}>＋ 新对话</button>{window.desktop&&<button className="quiet" onClick={()=>window.desktop?.showPet()}>显示小狗</button>}</div></header>
    <nav aria-label="功能">{([{key:'chat',label:'聊一聊'},{key:'library',label:'知识库'},{key:'tasks',label:'学习任务'},{key:'memory',label:'偏好与记忆'},{key:'history',label:'对话历史'},{key:'settings',label:'设置'}] as {key:PanelTab;label:string}[]).map(item=><button key={item.key} className={tab===item.key?'active':''} onClick={()=>{setTab(item.key);if(item.key==='tasks')loadTasks();if(item.key==='settings')loadLlmSettings();}}>{item.label}{item.key==='library'&&documents.length>0&&<span className="tab-count">{documents.length}</span>}</button>)}</nav>
    <div className="panel-body">
    {tab==='chat'&&<div className="chat-workspace"><section className="chat-transcript" aria-label="对话记录">{messages.length===0?<div className="chat-greeting"><div className="greeting-dog"><DogAvatar state={pet}/></div><span className="overline">ONE PAW AT A TIME</span><h2>今天也一起，学一点点。</h2><p>我能帮你查资料、记住学习习惯，<br/>也能陪你把计划变成一步步的小任务。</p><div className="greeting-actions"><button onClick={()=>setTab('library')}>＋ 上传学习资料</button><button className="quiet" onClick={()=>setInput('帮我制定复习数据库的学习计划，3天每天30分钟')}>试试制定学习计划 →</button></div></div>:messages.map(message=><article className={`chat-message ${message.role}`} key={message.id}><div className="chat-speaker">{message.role==='user'?'你':petName}{message.metadata?.mode&&<span className="answer-mode">{message.metadata.mode==='memory'?'个人记忆':['overview','summary','extractive_overview'].includes(message.metadata.mode)?'全文摘要':message.metadata.mode==='comparison'?'资料比较':message.metadata.mode==='general'?'普通聊天':message.metadata.mode==='review'||message.metadata.mode==='review_feedback'?'复习反馈':message.metadata.mode==='review_question'?'复习题':message.metadata.mode==='llm'?'依据资料回答':message.metadata.mode==='clarification'?'需要说明':message.metadata.mode==='no_evidence'?'资料不足':message.metadata.mode==='agent'?'学习助手':'检索原文'}</span>}</div>{message.metadata?.warning&&<p className="answer-warning">{message.metadata.warning}</p>}<div className="chat-content">{message.content.split(/(\[S\d+\])/g).map((part,i)=>{const citation=message.metadata?.sources?.find(s=>`[${s.id}]`===part);return citation?<button className="citation-button" key={i} onClick={()=>setSource(citation)}>{part}</button>:<React.Fragment key={i}>{part}</React.Fragment>;})}</div>{!!message.metadata?.sources?.length&&<div className="source-pills">{message.metadata.sources.map(s=><button key={s.id} onClick={()=>setSource(s)}><span>{s.id}</span>{s.filename} · {sourcePosition(s)}</button>)}</div>}{!!message.metadata?.review?.options?.length&&(message.metadata.mode==='review'||message.metadata.mode==='review_question')&&<div className="chat-review-options" role="group" aria-label="选择题选项">{message.metadata.review.options.map(option=><button key={option.key} type="button" disabled={sending||connection!=='已连接'} onClick={()=>sendText(option.key)}>{option.key}. {option.text}</button>)}</div>}</article>)}{sending&&<p className="thinking-line"><span/>{activity||'豆豆正在思考…'}</p>}<div ref={messagesEnd}/></section>{nextStep&&<div className="next-step-card" role="status"><strong>{nextStep.title}</strong><p>{nextStep.suggestion}</p><button type="button" disabled={sending||connection!=='已连接'} onClick={()=>{if(nextStep.action==='upload')setTab('library');else if(nextStep.action==='review_answer'){setInput(nextStep.placeholder||'');setTab('chat');}else if(nextStep.prompt)sendText(nextStep.prompt);}}>{nextStep.action==='review_answer'?'去输入框作答':('继续：'+(nextStep.prompt||nextStep.title||'').slice(0,18)+((nextStep.prompt||'').length>18?'…':''))}</button>{!!streak?.current_streak&&<span className="streak-chip">连续 {streak.current_streak} 天</span>}</div>}<div className="chat-quick-reviews" role="group" aria-label="一键学习"><button type="button" className="quiet" disabled={sending||connection!=='已连接'} onClick={()=>sendText('今日计划')}>今日计划</button><button type="button" className="quiet" disabled={sending||connection!=='已连接'} onClick={()=>sendText('今日小测')}>今日小测</button><button type="button" className="quiet" disabled={sending||connection!=='已连接'} onClick={()=>sendText('薄弱点回顾')}>薄弱点回顾</button><button type="button" className="quiet" disabled={sending||connection!=='已连接'} onClick={()=>sendText('开始复习')}>开始复习</button></div><form className="chat-composer" onSubmit={send}><textarea aria-label="消息" value={input} onChange={e=>setInput(e.target.value)} placeholder="问问资料里的内容，或告诉豆豆你的学习计划…" maxLength={4000} rows={2} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();sendText(input);}}}/><div className="composer-bottom"><select aria-label="资料检索范围" value={scope} onChange={e=>setScope(e.target.value)}><option value="auto">自动 · 知识与学习助手</option><option value="chat">普通聊天 · 不查知识库</option><option value="all">全部知识库</option>{scope==='selection'&&<option value="selection">已选 {shared.documentIds?.length||0} 份资料</option>}{documents.filter(d=>d.status==='ready'&&!d.needs_reindex).map(d=><option key={d.id} value={d.id}>{d.filename}</option>)}</select><button disabled={connection!=='已连接'||sending||!input.trim()}>{sending?'思考中…':'发送 ↑'}</button></div></form><details className="plan-options"><summary>把输入作为学习目标生成计划</summary><div className="controls"><label>计划天数<input aria-label="聊天计划天数" type="number" min={1} max={14} value={days} onChange={e=>setDays(Number(e.target.value))}/></label><label>每天分钟<input aria-label="聊天每日分钟" type="number" min={15} max={240} value={dailyMinutes} onChange={e=>setDailyMinutes(Number(e.target.value))}/></label><button onClick={planFromChat} disabled={!input.trim()||input.trim().length>200||sending||connection!=='已连接'}>生成待确认草稿</button></div></details>{draft&&<div className="draft"><h3>待确认的计划草稿</h3><ol>{(draft.steps||draft.schedule||[]).map((step,i)=><li key={i}>第 {step.day} 天 · {step.title} · {step.minutes} 分钟</li>)}</ol><button onClick={confirmDraft}>确认并保存任务</button><button className="quiet" onClick={()=>setDraft(null)}>取消</button></div>}</div>}
    {['library','memory','history'].includes(tab)&&<KnowledgePanels pane={tab as 'library'|'memory'|'history'} onOpenConversation={openConversation} onAsk={askKnowledge} onActivity={(state,text)=>{setPet(state);setActivity(text);}} onDocuments={()=>setDocumentVersion(v=>v+1)} onDeleteConversation={id=>{if(session.current===id){conversation.newChat();setDraft(null);}}}/>}
    {tab === 'tasks' && <section><h2>学习计划</h2><p className="streak-banner">骨头 {streak?.bones||0} · 已完成任务 {streak?.tasks_completed||0}{(streak?.current_streak)?` · 连续学习 ${streak.current_streak} 天`:''} · 累计专注 {streak?.total_focus_minutes||0} 分钟{(streak?.achievement_labels||streak?.achievements||[]).length?` · 成就：${(streak?.achievement_labels||streak?.achievements||[]).join('、')}`:''}</p><div className="bones-shop"><p className="muted">骨头用途：每个任务只能领一次。攒够后可花 {streak?.feed_cost||3} 根喂豆豆，换一句鼓励并让桌宠开心一下。</p><button type="button" onClick={feedPetWithBones} disabled={(streak?.bones||0)<(streak?.feed_cost||3)}>喂豆豆（{streak?.feed_cost||3} 骨头）</button></div><div className="controls"><input aria-label="学习目标" value={goal} onChange={e => setGoal(e.target.value)} placeholder="例如：复习数据库索引"/><label>天数<input aria-label="计划天数" type="number" min={1} max={14} value={days} onChange={e => setDays(Number(e.target.value))}/></label><label>每天分钟<input aria-label="每日分钟" type="number" min={15} max={240} value={dailyMinutes} onChange={e => setDailyMinutes(Number(e.target.value))}/></label></div><div className="controls"><button onClick={() => createDraft('plan')} disabled={!goal.trim()}>生成新计划</button><button onClick={() => createDraft('replan')}>重新安排未完成任务</button></div>{draft && <div className="draft"><h3>计划草稿（尚未保存）</h3><p>{draft.reason}</p><ol>{(draft.steps || draft.schedule || []).map((step, i) => <li key={i}>第 {step.day} 天 · {step.title} · {step.minutes} 分钟</li>)}</ol><button onClick={confirmDraft}>确认并保存</button><button onClick={() => setDraft(null)}>取消</button></div>}<h2>学习任务</h2><form onSubmit={addTask}><input aria-label="新任务" value={taskTitle} onChange={e => setTaskTitle(e.target.value)} placeholder="例如：复习数据库索引" maxLength={200}/><button>添加</button></form><ul className="task-list">{tasks.map(task => <li key={task.id}><label><input type="checkbox" checked={task.done} onChange={() => toggleTask(task)}/><span className={task.done ? 'done' : ''}>{task.title} · {task.estimated_minutes} 分钟{task.scheduled_day ? ` · 第 ${task.scheduled_day} 天` : ''}{task.bones_awarded ? ' · 已领过骨头' : ''}</span></label><button type="button" onClick={() => editTask(task)}>修改</button><button type="button" className="quiet" onClick={() => deleteTask(task)}>删除</button></li>)}</ul><div className="trash-panel"><button type="button" className="quiet trash-toggle" onClick={() => setShowTrash(v => !v)}>回收站{trash.length ? `（${trash.length}）` : ''}{showTrash ? ' ▾' : ' ▸'}</button>{showTrash && (trash.length ? <ul className="task-list trash-list">{trash.map(task => <li key={task.id}><span className="trash-title">{task.title} · {task.estimated_minutes} 分钟{task.scheduled_day ? ` · 第 ${task.scheduled_day} 天` : ''}{task.done ? ' · 已完成' : ''}</span><button type="button" onClick={() => restoreTask(task)}>恢复</button><button type="button" className="quiet" onClick={() => purgeTask(task)}>永久删除</button></li>)}</ul> : <p className="muted trash-empty">回收站是空的。</p>)}</div><h2>专注计时</h2>{focus.id ? <div><strong>{Math.floor(focus.remaining_seconds / 60)}:{String(focus.remaining_seconds % 60).padStart(2, '0')}</strong><button onClick={stopFocus}>结束</button></div> : <div className="controls"><input aria-label="专注分钟" type="number" min={1} max={240} value={focusMinutes} onChange={e => setFocusMinutes(Number(e.target.value))}/><button onClick={startFocus}>开始专注</button></div>}<h2>交互式复习</h2><div className="controls"><input aria-label="复习知识点" value={reviewTopic} onChange={e => setReviewTopic(e.target.value)} placeholder="例如：B+树"/><button onClick={startReview} disabled={!reviewTopic.trim()}>开始复习</button><button className="quiet" onClick={async()=>{try{const quiz=await requestJson('/reviews/daily-quiz','POST',{session_id:session.current,...scopeFields(scope)});setReview(quiz.items?.[0]||null);setReviewFeedback('');setNotice(`今日小测 ${quiz.count} 题已就绪`);}catch(e){setNotice(String(e));}}}>今日小测</button><button className="quiet" onClick={async()=>{try{const item=await requestJson('/reviews/weak-point','POST',{session_id:session.current,...scopeFields(scope)});setReview(item);setReviewFeedback('');setNotice('已挑出薄弱点回顾题');}catch(e){setNotice(String(e));}}}>薄弱点回顾</button></div>{review && <div className="review-card"><p className="review-stem">{review.stem || review.question}</p>{!!review.options?.length && <div className="review-options" role="group" aria-label="选项">{review.options.map(option=><button key={option.key} type="button" className={reviewAnswer===option.key?'active':''} onClick={()=>pickReviewOption(option)}><span>{option.key}</span>{option.text}</button>)}</div>}{(!review.options?.length || !['multiple_choice','true_false'].includes(review.question_type||'')) && <><textarea aria-label="我的回答" value={reviewAnswer} onChange={e => setReviewAnswer(e.target.value)} placeholder={review.question_type==='fill_blank'?'填入关键词…':'用自己的话作答…'}/><button onClick={()=>submitReview()} disabled={!reviewAnswer.trim()}>提交回答</button></>}</div>}{reviewFeedback && <p role="status">{reviewFeedback}</p>}</section>}
    {tab === 'settings' && <section className="settings-panel"><h2>设置</h2><form onSubmit={saveName}><label htmlFor="pet-name">桌宠名字</label><input id="pet-name" value={petName} onChange={e => setPetName(e.target.value)} maxLength={100}/><button>保存</button></form>{window.desktop && <button type="button" onClick={() => window.desktop?.showPet()}>显示悬浮桌宠</button>}<h2>模型与 API</h2><p className="muted">{llm.hint || '选择离线或在线；在线模式使用你自己的 OpenAI 兼容接口。'}</p><form className="llm-settings" onSubmit={saveLlmSettings}><label>运行模式<select aria-label="运行模式" value={llm.mode} onChange={e=>setLlm(prev=>({...prev,mode:e.target.value as 'offline'|'online'}))}><option value="offline">离线 · 本地检索与模板</option><option value="online">在线 · 使用我的 API</option></select></label><label>接口预设<select aria-label="接口预设" value={llm.provider} onChange={e=>applyPreset(e.target.value)} disabled={llm.mode!=='online'}>{(llm.presets||[{id:'custom',label:'自定义 OpenAI 兼容接口',base_url:'',model:''}]).map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label><label>模型名<input aria-label="模型名" value={llm.llm_model} onChange={e=>setLlm(prev=>({...prev,llm_model:e.target.value}))} placeholder="例如：qwen-plus / gpt-4o-mini" disabled={llm.mode!=='online'} maxLength={120}/></label><label>Base URL<input aria-label="Base URL" value={llm.llm_base_url} onChange={e=>setLlm(prev=>({...prev,llm_base_url:e.target.value}))} placeholder="https://…/compatible-mode/v1" disabled={llm.mode!=='online'} maxLength={300}/></label><label>API Key<input aria-label="API Key" type="password" value={llm.llm_api_key} onChange={e=>setLlm(prev=>({...prev,llm_api_key:e.target.value}))} placeholder={llm.has_api_key?`已保存 ${llm.api_key_masked||''}（留空则保留）`:'填写你的密钥'} disabled={llm.mode!=='online'} maxLength={200} autoComplete="off"/></label><button disabled={llmBusy}>{llmBusy?'保存中…':'保存模型设置'}</button></form><p>当前：{llm.mode==='online'?(llm.online_ready?'在线已就绪 · 复习批改走你的 API':'在线未就绪 · 请补全模型/密钥/地址'):'离线模式'} · Agent {mode==='demo'?'演示':'LangChain'}</p></section>}
    </div><footer className="app-footer" role="status"><span>♡ {notice||'每一点积累，都算数。'}</span><span>{labels[pet]}</span></footer>
    {source&&<div className="source-overlay" onClick={()=>setSource(null)}><div className="source-dialog" role="dialog" aria-modal="true" aria-label="引用原文" onClick={e=>e.stopPropagation()}><header><div><span className="overline">BACK TO THE SOURCE</span><h3>{source.filename}</h3><p>{source.id} · {sourcePosition(source)}</p></div><button className="quiet" aria-label="关闭引用" onClick={()=>setSource(null)}>×</button></header><pre>{source.snippet}</pre><footer><span>引用保留的是该轮回答时的原文快照。</span><div className="source-footer-actions"><button type="button" className="quiet" onClick={bookmarkSource}>收藏重点</button><a href={`${api}/knowledge/documents/${source.document_id}/source`} target="_blank" rel="noreferrer">下载原文件 ↗</a></div></footer></div></div>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
