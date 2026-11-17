import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChatWorkspace } from './ChatWorkspace';
import { ChatInputDock } from './ChatInputDock';
import { GlobalCareRail } from './GlobalCareRail';
import { TasksWorkspace } from './TasksWorkspace';
import { buildLearningCareItems, fallbackCareItems } from './careTimeline';
import { createRoot } from 'react-dom/client';
import { messageEvent, parseHitlRequired, parseServerEvent, type PetState } from './protocol';
import { DogAvatar } from './DogAvatar';
import { KnowledgePanels } from './KnowledgePanels';
import { api,request,sourcePosition,type ChatMessage,type Source,type KnowledgeDocument,type LearningNextStep,type LearningProject,type ReviewChoice } from './knowledge';
import { ProjectSidebar } from './ProjectSidebar';
import type { PanelTab } from './desktop';
import './desktop';
import { conversation, useConversation, scopeFields } from './chatStore';
import './style.css';
import './features.css';
import './shell-layout.css';
import './pawprint-timeline.css';
import './pawprint-ui.css';
import { bindStickToBottom, scrollToBottom } from './scrollToBottom';

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
  const transcriptRef=useRef<HTMLElement>(null);
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
  const dismissedDraft = useRef<number | null>(null);
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
  type LearnerProfile = { answer_style: 'concise' | 'detailed' | 'socratic'; tone: string; language: string; background: string; notes: string };
  const [learner, setLearner] = useState<LearnerProfile>({ answer_style: 'concise', tone: 'friendly', language: 'zh', background: '', notes: '' });
  const [learnerBusy, setLearnerBusy] = useState(false);
  const [projects, setProjects] = useState<LearningProject[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [projectBusy, setProjectBusy] = useState(false);
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  async function loadProjects() {
    let list = await request<LearningProject[]>('/knowledge/projects');
    if (!list.length) {
      const created = await request<LearningProject>('/knowledge/projects/ensure-default', { method: 'POST' });
      list = [created];
    }
    setProjects(list);
    return list;
  }

  async function activateProject(project: LearningProject, opts?: { force?: boolean }) {
    if (sending && !opts?.force) {
      setNotice('等当前回复完成后再切换学习夹。');
      return;
    }
    setActiveProjectId(project.id);
    localStorage.setItem('companion-active-project', project.id);
    setTab('chat');
    try {
      const msgs = await request<ChatMessage[]>(`/knowledge/sessions/${project.session_id}/messages`);
      const scope =
        project.document_ids.length === 1
          ? project.document_ids[0]
          : project.document_ids.length > 1
            ? 'selection'
            : 'auto';
      conversation.open(project.session_id, msgs, scope, project.document_ids);
      setDraft(null);
    } catch (e) {
      setNotice(String(e));
    }
  }

  async function createProject() {
    const name = window.prompt('新学习夹名称', '新学习夹');
    if (!name?.trim()) return;
    setProjectBusy(true);
    try {
      const project = await request<LearningProject>('/knowledge/projects', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim() }),
      });
      await loadProjects();
      await activateProject(project, { force: true });
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

  async function renameProject(project: LearningProject, nextName: string) {
    const name = nextName.trim().slice(0, 40);
    if (!name || name === project.name) return;
    setProjectBusy(true);
    try {
      const updated = await request<LearningProject>(`/knowledge/projects/${project.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name }),
      });
      setProjects((list) => list.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)));
      await loadProjects();
      setNotice(`已重命名为「${updated.name}」`);
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

  async function deleteProject(project: LearningProject) {
    if (!confirm(`删除学习夹「${project.name}」及其对话？`)) return;
    setProjectBusy(true);
    try {
      await request(`/knowledge/projects/${project.id}`, { method: 'DELETE' });
      const list = await loadProjects();
      if (activeProjectId === project.id) {
        const next = list[0];
        if (next) await activateProject(next, { force: true });
        else conversation.newChat();
      }
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

  async function attachProjectFile(projectId: string, documentId: string) {
    setProjectBusy(true);
    try {
      const updated = await request<LearningProject>(`/knowledge/projects/${projectId}/documents`, {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId }),
      });
      await loadProjects();
      if (activeProjectId === projectId) await activateProject(updated, { force: true });
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

  async function detachProjectFile(projectId: string, documentId: string) {
    setProjectBusy(true);
    try {
      await request(`/knowledge/projects/${projectId}/documents/${documentId}`, { method: 'DELETE' });
      const list = await loadProjects();
      const updated = list.find((p) => p.id === projectId);
      if (updated && activeProjectId === projectId) await activateProject(updated, { force: true });
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

  async function uploadToProject(projectId: string, files: FileList | File[]) {
    setProjectBusy(true);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append('file', file);
        const doc = await request<KnowledgeDocument>('/knowledge/documents', { method: 'POST', body: form });
        await request(`/knowledge/projects/${projectId}/documents`, {
          method: 'POST',
          body: JSON.stringify({ document_id: doc.id }),
        });
      }
      setDocumentVersion((v) => v + 1);
      const list = await loadProjects();
      const updated = list.find((p) => p.id === projectId);
      if (updated) await activateProject(updated, { force: true });
      setNotice('文件已加入学习夹。');
    } catch (e) {
      setNotice(String(e));
    } finally {
      setProjectBusy(false);
    }
  }

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
    const incoming=latest?.metadata?.draft;
    if(incoming && incoming.id!==dismissedDraft.current){
      setDraft(incoming);
      setDraftKind(latest?.metadata?.kind||'plan');
    }
    if(latest?.metadata?.next_step)setNextStep(latest.metadata.next_step);
  },[messages]);
  useEffect(() => {
    void (async () => {
      try {
        const list = await loadProjects();
        const saved = localStorage.getItem('companion-active-project');
        const pick = list.find((p) => p.id === saved) || list[0];
        if (pick) await activateProject(pick, { force: true });
      } catch (e) {
        setNotice(String(e));
      }
    })();
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
          const raw = String(event.data);
          const parsed = JSON.parse(raw) as { type?: string };
          if (parsed.type === 'hitl_required') {
            const hitl = parseHitlRequired(raw);
            if (conversation.receiveHitl(hitl)) {
              setPet(hitl.state);
              setActivity(hitl.text);
            }
            return;
          }
          const data = parseServerEvent(raw);
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
  useEffect(() => {
    if (tab !== 'chat') return;
    const el = transcriptRef.current;
    if (!el) return;
    return bindStickToBottom(el);
  }, [tab, messages.length]);
  useEffect(() => {
    if (tab !== 'chat') return;
    scrollToBottom(transcriptRef.current, { smooth: !sending, force: true });
  }, [messages, sending, tab, activity, shared.status?.text]);
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
        const sid = session.current;
        const query = sid ? `?chat_session=${encodeURIComponent(sid)}` : '';
        const result = await requestJson(`/focus/${sessionId}/finish${query}`, 'POST');
        setFocus({ id: null, remaining_seconds: 0 });
        setPet('success');
        setActivity(text);
        if (result.streak) setStreak(result.streak);
        if (result.next_step) setNextStep(result.next_step);
        pushCheckinReview(result.followup_review);
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
  function newChat() {
    if (sending) return;
    void createProject();
  }
  function submitHitl(payload: Record<string, string | number>, action?: string) {
    const hitl = shared.pendingHitl;
    if (!hitl || !socket.current || socket.current.readyState !== WebSocket.OPEN) return;
    socket.current.send(JSON.stringify({
      type: 'graph_resume',
      kind: hitl.kind,
      thread_id: hitl.interruptId,
      session_id: session.current,
      request_id: hitl.requestId,
      payload: action ? { ...payload, action } : payload,
      ...scopeFields(scope),
    }));
    setActivity('正在继续…');
    setPet('thinking');
  }
  async function loadLearnerProfile() {
    try {
      const data = await requestJson('/learner/profile', 'GET') as LearnerProfile;
      setLearner(data);
    } catch { /* ignore */ }
  }
  async function saveLearnerProfile(e: React.FormEvent) {
    e.preventDefault();
    setLearnerBusy(true);
    try {
      const data = await requestJson('/learner/profile', 'PUT', learner) as LearnerProfile;
      setLearner(data);
      setNotice('学习者偏好已保存。');
    } catch (err) {
      setNotice(String(err));
    } finally {
      setLearnerBusy(false);
    }
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
  async function deleteLearningPlan() {
    const planCount = tasks.filter((t) => t.scheduled_day != null).length;
    if (planCount === 0) {
      setNotice('当前没有带排期的学习计划。');
      return;
    }
    if (
      !confirm(
        `将 ${planCount} 条学习计划任务移到回收站？\n无「第 X 天」排期的手动任务会保留；可从回收站恢复计划任务。`,
      )
    ) {
      return;
    }
    try {
      const result = (await requestJson('/tasks/plan', 'DELETE')) as { deleted?: number };
      setDraft(null);
      await loadTasks();
      setNotice(result.deleted ? `已移除 ${result.deleted} 条学习计划任务。` : '没有可删除的计划任务。');
    } catch (e) {
      setNotice(String(e));
    }
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
  function closeDraft(next: PlanDraft | null = null) {
    if (next) {
      dismissedDraft.current = null;
      setDraft(next);
      return;
    }
    if (draft?.id != null) dismissedDraft.current = draft.id;
    setDraft(null);
  }
  async function confirmDraft() {
    if (!draft) return;
    try {
      setPet('tool'); setActivity('正在保存计划');
      await requestJson(`/plans/${draftKind === 'plan' ? 'drafts' : 'replan-drafts'}/${draft.id}/confirm`, 'POST');
      dismissedDraft.current = draft.id;
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
  function pushCheckinReview(follow?: { question?: string } & Record<string, unknown>) {
    if (!follow?.question) return;
    conversation.setMessages((msgs) => [...msgs, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: follow.question || '',
      metadata: { mode: 'review_question', review: follow as import('./knowledge').ReviewPayload },
    }]);
  }
  async function startFocus() {
    try { setFocus(await requestJson('/focus', 'POST', { minutes: focusMinutes })); setPet('tool'); setActivity('专注计时已开始'); }
    catch (e) { setNotice(String(e)); }
  }
  async function stopFocus() {
    if (!focus.id) return;
    try {
      const sid = session.current;
      const query = sid ? `?chat_session=${encodeURIComponent(sid)}` : '';
      const result = await requestJson(`/focus/${focus.id}/finish${query}`, 'POST');
      setFocus({ id: null, remaining_seconds: 0 });
      setPet('success'); setActivity('专注已结束');
      if (result.streak) setStreak(result.streak);
      if (result.next_step) setNextStep(result.next_step);
      pushCheckinReview(result.followup_review);
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
    try {
      const result = await requestJson(`/reviews/${review.id}/answer`, 'POST', { answer: answer.trim() });
      setReviewFeedback(result.feedback);
      setReviewAnswer('');
      if (result.next_review?.question) {
        setReview(result.next_review);
        setActivity(`第 ${result.next_review.quiz_index || ''} 题`);
      } else {
        setReview(null);
        setPet('success');
        setActivity('复习反馈已生成');
      }
    }
    catch (e) { setNotice(String(e)); }
  }
  async function pickReviewOption(option: ReviewChoice) {
    setReviewAnswer(option.key);
    await submitReview(option.key);
  }
  const [careRailOpen, setCareRailOpen] = useState(
    () => typeof localStorage !== 'undefined' && localStorage.getItem('companion-care-rail') !== 'hidden',
  );
  const careItems = useMemo(() => {
    const built = buildLearningCareItems(tasks, nextStep);
    return built.length ? built : fallbackCareItems();
  }, [tasks, nextStep]);
  const nextStepActionLabel =
    nextStep?.action === 'review_answer'
      ? '去输入框作答'
      : nextStep
        ? `继续：${(nextStep.prompt || nextStep.title || '').slice(0, 18)}${(nextStep.prompt || '').length > 18 ? '…' : ''}`
        : undefined;

  function runNextStep() {
    if (!nextStep) return;
    if (nextStep.action === 'upload') setTab('library');
    else if (nextStep.action === 'review_answer') {
      setInput(nextStep.placeholder || '');
      setTab('chat');
    } else if (nextStep.prompt) sendText(nextStep.prompt);
  }

  async function markCareTask(taskId: number) {
    const task = tasks.find((t) => t.id === taskId);
    if (task && !task.done) await toggleTask(task);
  }

  async function undoCareTask(taskId: number) {
    const task = tasks.find((t) => t.id === taskId);
    if (task?.done) await toggleTask(task);
  }

  function editCareTask(taskId: number) {
    const task = tasks.find((t) => t.id === taskId);
    if (task) void editTask(task);
  }

  function deleteCareTask(taskId: number) {
    const task = tasks.find((t) => t.id === taskId);
    if (task) void deleteTask(task);
  }

  const tabTitles: Record<PanelTab, string> = {
    chat: activeProject?.name || '聊天',
    library: '资料库',
    tasks: '任务',
    memory: '偏好',
    history: '历史',
    settings: '设置',
  };
  const statusLine = `${connection} · ${labels[pet]}${mode === 'demo' ? ' · 离线' : ' · 已配置模型'}`;

  return <main className="companion-panel companion-shell">
    <ProjectSidebar
      petName={petName}
      petState={pet}
      tab={tab}
      documents={documents}
      projects={projects}
      activeProjectId={activeProjectId}
      libraryCount={documents.length}
      busy={projectBusy || sending}
      onShowPet={() => window.desktop?.showPet()}
      onSelectTab={(next) => {
        setTab(next);
        if (next === 'tasks') loadTasks();
        if (next === 'settings') {
          loadLlmSettings();
          loadLearnerProfile();
        }
      }}
      onSelectProject={(project) => void activateProject(project)}
      onCreateProject={() => void createProject()}
      onRenameProject={(project, name) => renameProject(project, name)}
      onDeleteProject={(project) => void deleteProject(project)}
      onAttachFile={attachProjectFile}
      onDetachFile={detachProjectFile}
      onUploadToProject={(id, files) => void uploadToProject(id, files)}
    />
    <div className="app-main">
    <header className="app-header">
      <div>
        <h1 className="app-title">{tabTitles[tab]}</h1>
        <p className="app-status"><span className={`connection-dot ${connection === '已连接' ? 'online' : ''}`} />{statusLine}</p>
      </div>
      <div className="header-actions">
        <button type="button" className="quiet" disabled={sending || projectBusy} onClick={newChat}>新学习夹</button>
        {window.desktop && <button type="button" className="quiet" onClick={() => window.desktop?.showPet()}>桌宠</button>}
      </div>
    </header>
    <div className={`panel-body${tab === 'chat' ? ' panel-body--chat' : ''}`}>
    <div className="panel-scroll">
    <div className={`content-canvas${tab === 'chat' ? ' content-canvas-chat' : ''}`}>
    {tab==='chat'&&<ChatWorkspace petName={petName} messages={messages} sending={sending} connection={connection} activity={activity} setInput={setInput} onOpenLibrary={()=>setTab('library')} transcriptRef={transcriptRef} messagesEndRef={messagesEnd} sendText={sendText} setSource={setSource} draft={draft} setDraft={closeDraft} confirmDraft={confirmDraft} />}
        {['library','memory','history'].includes(tab)&&<div className="page-card knowledge-shell"><KnowledgePanels pane={tab as 'library'|'memory'|'history'} onOpenConversation={openConversation} onAsk={askKnowledge} onActivity={(state,text)=>{setPet(state);setActivity(text);}} onDocuments={()=>{setDocumentVersion(v=>v+1);void loadProjects();}} onDeleteConversation={id=>{if(session.current===id){conversation.newChat();setDraft(null);}void loadProjects();}} /></div>}
    {tab === 'tasks' && (
      <>
        <TasksWorkspace
          streak={streak}
          goal={goal}
          setGoal={setGoal}
          days={days}
          setDays={setDays}
          dailyMinutes={dailyMinutes}
          setDailyMinutes={setDailyMinutes}
          draft={draft}
          setDraft={closeDraft}
          createDraft={createDraft}
          confirmDraft={confirmDraft}
          taskTitle={taskTitle}
          setTaskTitle={setTaskTitle}
          addTask={addTask}
          feedPetWithBones={feedPetWithBones}
          trash={trash}
          showTrash={showTrash}
          setShowTrash={setShowTrash}
          restoreTask={restoreTask}
          purgeTask={purgeTask}
          planTaskCount={tasks.filter((t) => t.scheduled_day != null).length}
          onDeleteLearningPlan={() => void deleteLearningPlan()}
        />
        <section className="page-card"><h2>专注计时</h2>{focus.id ? <div><strong>{Math.floor(focus.remaining_seconds / 60)}:{String(focus.remaining_seconds % 60).padStart(2, '0')}</strong><button onClick={stopFocus}>结束</button></div> : <div className="controls"><input aria-label="专注分钟" type="number" min={1} max={240} value={focusMinutes} onChange={e => setFocusMinutes(Number(e.target.value))}/><button onClick={startFocus}>开始专注</button></div>}<h2>交互式复习</h2><div className="controls"><input aria-label="复习知识点" value={reviewTopic} onChange={e => setReviewTopic(e.target.value)} placeholder="例如：B+树"/><button onClick={startReview} disabled={!reviewTopic.trim()}>开始复习</button><button className="quiet" onClick={async()=>{try{const quiz=await requestJson('/reviews/daily-quiz','POST',{session_id:session.current,...scopeFields(scope)});setReview(quiz.items?.[0]||null);setReviewFeedback('');setNotice(`今日小测 ${quiz.count} 题，先做第 1 题`);}catch(e){setNotice(String(e));}}}>今日小测</button><button className="quiet" onClick={async()=>{try{const item=await requestJson('/reviews/weak-point','POST',{session_id:session.current,...scopeFields(scope)});setReview(item);setReviewFeedback('');setNotice('已挑出薄弱点回顾题');}catch(e){setNotice(String(e));}}}>薄弱点回顾</button></div>{review && <div className="review-card"><p className="review-stem">{review.stem || review.question}</p>{!!review.options?.length && <div className="review-options" role="group" aria-label="选项">{review.options.map(option=><button key={option.key} type="button" className={reviewAnswer===option.key?'active':''} onClick={()=>pickReviewOption(option)}><span>{option.key}</span>{option.text}</button>)}</div>}{(!review.options?.length || !['multiple_choice','true_false'].includes(review.question_type||'')) && <><textarea aria-label="我的回答" value={reviewAnswer} onChange={e => setReviewAnswer(e.target.value)} placeholder={review.question_type==='fill_blank'?'填入关键词…':'用自己的话作答…'}/><button onClick={()=>submitReview()} disabled={!reviewAnswer.trim()}>提交回答</button></>}</div>}{reviewFeedback && <p role="status">{reviewFeedback}</p>}</section>
      </>
    )}
    {tab === 'settings' && <section className="settings-panel page-card"><h2>设置</h2><form onSubmit={saveName}><label htmlFor="pet-name">桌宠名字</label><input id="pet-name" value={petName} onChange={e => setPetName(e.target.value)} maxLength={100}/><button>保存</button></form>{window.desktop && <button type="button" onClick={() => window.desktop?.showPet()}>显示悬浮桌宠</button>}<h2>学习者画像</h2><p className="muted">影响答题表达方式，不会覆盖知识库证据约束。</p><form className="learner-settings" onSubmit={saveLearnerProfile}><label>回答风格<select aria-label="回答风格" value={learner.answer_style} onChange={e=>setLearner(prev=>({...prev,answer_style:e.target.value as LearnerProfile['answer_style']}))}><option value="concise">简洁</option><option value="detailed">详细分点</option><option value="socratic">启发式提问</option></select></label><label>语气<input aria-label="语气" value={learner.tone} onChange={e=>setLearner(prev=>({...prev,tone:e.target.value}))} maxLength={40}/></label><label>语言<input aria-label="语言" value={learner.language} onChange={e=>setLearner(prev=>({...prev,language:e.target.value}))} maxLength={16}/></label><label>背景<textarea aria-label="背景" value={learner.background} onChange={e=>setLearner(prev=>({...prev,background:e.target.value}))} maxLength={600} rows={3}/></label><label>补充备注<textarea aria-label="补充备注" value={learner.notes} onChange={e=>setLearner(prev=>({...prev,notes:e.target.value}))} maxLength={300} rows={2}/></label><button disabled={learnerBusy}>{learnerBusy?'保存中…':'保存学习者画像'}</button></form><h2>模型与 API</h2><p className="muted">{llm.hint || '选择离线或在线；在线模式使用你自己的 OpenAI 兼容接口。'}</p><form className="llm-settings" onSubmit={saveLlmSettings}><label>运行模式<select aria-label="运行模式" value={llm.mode} onChange={e=>setLlm(prev=>({...prev,mode:e.target.value as 'offline'|'online'}))}><option value="offline">离线 · 本地检索与模板</option><option value="online">在线 · 使用我的 API</option></select></label><label>接口预设<select aria-label="接口预设" value={llm.provider} onChange={e=>applyPreset(e.target.value)} disabled={llm.mode!=='online'}>{(llm.presets||[{id:'custom',label:'自定义 OpenAI 兼容接口',base_url:'',model:''}]).map(p=><option key={p.id} value={p.id}>{p.label}</option>)}</select></label><label>模型名<input aria-label="模型名" value={llm.llm_model} onChange={e=>setLlm(prev=>({...prev,llm_model:e.target.value}))} placeholder="例如：qwen-plus / gpt-4o-mini" disabled={llm.mode!=='online'} maxLength={120}/></label><label>Base URL<input aria-label="Base URL" value={llm.llm_base_url} onChange={e=>setLlm(prev=>({...prev,llm_base_url:e.target.value}))} placeholder="https://…/compatible-mode/v1" disabled={llm.mode!=='online'} maxLength={300}/></label><label>API Key<input aria-label="API Key" type="password" value={llm.llm_api_key} onChange={e=>setLlm(prev=>({...prev,llm_api_key:e.target.value}))} placeholder={llm.has_api_key?`已保存 ${llm.api_key_masked||''}（留空则保留）`:'填写你的密钥'} disabled={llm.mode!=='online'} maxLength={200} autoComplete="off"/></label><button disabled={llmBusy}>{llmBusy?'保存中…':'保存模型设置'}</button></form><p>当前：{llm.mode==='online'?(llm.online_ready?'在线已就绪 · 复习批改走你的 API':'在线未就绪 · 请补全模型/密钥/地址'):'离线模式'} · Agent {mode==='demo'?'演示':'LangChain'}</p></section>}
    </div>
    </div>
    <GlobalCareRail
        petName={petName}
        items={careItems}
        open={careRailOpen}
        onDismiss={() => {
          setCareRailOpen(false);
          localStorage.setItem('companion-care-rail', 'hidden');
        }}
        onOpen={() => {
          setCareRailOpen(true);
          localStorage.removeItem('companion-care-rail');
        }}
        streakDays={streak?.current_streak}
        onPrimaryAction={nextStep ? runNextStep : undefined}
        primaryActionLabel={nextStepActionLabel}
        primaryDisabled={sending || connection !== '已连接'}
        onMarkTaskDone={markCareTask}
        onUndoTaskDone={undoCareTask}
        onEditTask={editCareTask}
        onDeleteTask={deleteCareTask}
        nextStepSuggestion={nextStep?.suggestion}
      />
    {tab === 'chat' && (
      <ChatInputDock
        connection={connection}
        sending={sending}
        input={input}
        setInput={setInput}
        scope={scope}
        setScope={setScope}
        documents={documents}
        sharedDocCount={shared.documentIds?.length || 0}
        send={send}
        sendText={sendText}
        pendingHitl={shared.pendingHitl}
        submitHitl={submitHitl}
        cancelHitl={() => conversation.cancelHitl()}
        sessionId={shared.sessionId}
        days={days}
        setDays={setDays}
        dailyMinutes={dailyMinutes}
        setDailyMinutes={setDailyMinutes}
        planFromChat={planFromChat}
        draft={draft}
      />
    )}
    </div>
    <footer className="app-footer" role="status">
      <span className="footer-notice">{notice || '专注一点，慢慢学完'}</span>
    </footer>
    </div>
    {source&&<div className="source-overlay" onClick={()=>setSource(null)}><div className="source-dialog" role="dialog" aria-modal="true" aria-label="引用原文" onClick={e=>e.stopPropagation()}><header><div><h3>{source.filename}</h3><p>{source.id} · {sourcePosition(source)}</p></div><button type="button" className="quiet" aria-label="关闭" onClick={()=>setSource(null)}>×</button></header><pre>{source.snippet}</pre><footer><div className="source-footer-actions"><button type="button" className="quiet" onClick={bookmarkSource}>收藏</button><a href={`${api}/knowledge/documents/${source.document_id}/source`} target="_blank" rel="noreferrer">下载原文件</a></div></footer></div></div>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
